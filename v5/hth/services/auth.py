"""Users and authentication.  Passwords are PBKDF2-HMAC-SHA256 with a per-user salt."""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time

from hth.db.connection import Database
from hth.domain.constants import AuditCode
from hth.domain.models import User
from hth.services.audit import AuditService
from hth.services.permissions import ROLES

log = logging.getLogger(__name__)

PBKDF2_ITERATIONS = 200_000
MIN_PASSWORD_LENGTH = 4
MAX_FAILED_ATTEMPTS = 5  # then the username is locked out for LOCKOUT_SECONDS (doubling)
LOCKOUT_SECONDS = 30

# username (lower case) -> (consecutive failures, monotonic time the lockout ends).
# Process-wide on purpose: every AuthService instance shares it.
_failures: dict[str, tuple[int, float]] = {}

# (username, password, full name, role).  Change these passwords after first login.
DEFAULT_USERS: list[tuple[str, str, str, str]] = [
    ("admin", "admin", "Administrator", "admin"),
    ("emp1", "emp1", "Employee 1", "employee"),
]


class AuthError(Exception):
    pass


def _row_to_user(row) -> User:
    return User(
        id=row["id"],
        username=row["username"],
        full_name=row["full_name"],
        role=row["role"],
        is_active=bool(row["is_active"]),
    )


class AuthService:
    def __init__(self, db: Database):
        self.db = db
        self.audit = AuditService(db)

    # Hashing ----------------------------------------------------------------------
    @staticmethod
    def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
        salt = salt or secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS)
        return digest.hex(), salt

    # Bootstrap --------------------------------------------------------------------
    def ensure_default_users(self) -> None:
        if self.db.fetchone("SELECT 1 FROM users LIMIT 1") is not None:
            return
        for username, password, full_name, role in DEFAULT_USERS:
            self.create_user(username, password, full_name, role, actor="system")
        log.warning("Seeded default users (admin/admin, emp1/emp1) - change these passwords.")

    # Queries ----------------------------------------------------------------------
    def list_users(self) -> list[User]:
        return [_row_to_user(r) for r in self.db.fetchall("SELECT * FROM users ORDER BY id")]

    def get_user(self, user_id: int) -> User | None:
        row = self.db.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
        return _row_to_user(row) if row else None

    def verify(self, username: str, password: str) -> User | None:
        """The active user with these credentials, or None.  No audit entry, no lockout."""
        row = self.db.fetchone("SELECT * FROM users WHERE username = ?", (username.strip(),))
        if row is None or not row["is_active"]:
            return None
        computed, _ = self.hash_password(password, row["salt"])
        if not hmac.compare_digest(computed, row["password_hash"]):
            return None
        return _row_to_user(row)

    @staticmethod
    def lockout_remaining(username: str) -> int:
        """Seconds until ``username`` may try again (0 = now)."""
        _count, until = _failures.get(username.strip().lower(), (0, 0.0))
        return max(0, int(until - time.monotonic() + 0.999))

    def authenticate(self, username: str, password: str) -> User | None:
        """Sign-in: like :meth:`verify`, plus the audit log and a lockout after repeated failures.

        Raises AuthError while the username is locked out."""
        key = username.strip().lower()
        wait = self.lockout_remaining(key)
        if wait:
            raise AuthError(f"Too many failed attempts - try again in {wait} s.")
        user = self.verify(username, password)
        if user is None:
            count = _failures.get(key, (0, 0.0))[0] + 1
            until = 0.0
            if count >= MAX_FAILED_ATTEMPTS:
                until = time.monotonic() + LOCKOUT_SECONDS * 2 ** (count - MAX_FAILED_ATTEMPTS)
            _failures[key] = (count, until)
            self.audit.log(AuditCode.LOGIN, f"failed login for {username.strip()!r} (attempt {count})", "system")
            return None
        _failures.pop(key, None)
        self.audit.log(AuditCode.LOGIN, f"login {user.username}", username=user.username)
        return user

    # Mutations --------------------------------------------------------------------
    def create_user(self, username: str, password: str, full_name: str, role: str, actor: str = "system") -> User:
        username = username.strip()
        if not username:
            raise AuthError("Username is required.")
        if role not in ROLES:
            raise AuthError(f"Unknown role '{role}'.")
        if len(password) < MIN_PASSWORD_LENGTH:
            raise AuthError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
        if self.db.fetchone("SELECT 1 FROM users WHERE username = ?", (username,)):
            raise AuthError(f"User '{username}' already exists.")
        pw_hash, salt = self.hash_password(password)
        user_id = self.db.execute(
            "INSERT INTO users (username, full_name, role, password_hash, salt) VALUES (?, ?, ?, ?, ?)",
            (username, full_name.strip(), role, pw_hash, salt),
        )
        self.audit.log(AuditCode.USER, f"created user {username} ({role})", username=actor)
        return self.get_user(user_id)  # type: ignore[return-value]

    def set_password(self, user_id: int, new_password: str, actor: str) -> None:
        if len(new_password) < MIN_PASSWORD_LENGTH:
            raise AuthError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
        pw_hash, salt = self.hash_password(new_password)
        self.db.execute("UPDATE users SET password_hash = ?, salt = ? WHERE id = ?", (pw_hash, salt, user_id))
        user = self.get_user(user_id)
        self.audit.log(AuditCode.USER, f"password changed for {user.username if user else user_id}", actor)

    def change_own_password(self, user: User, old_password: str, new_password: str) -> None:
        if self.verify(user.username, old_password) is None:
            raise AuthError("Current password is incorrect.")
        self.set_password(user.id, new_password, actor=user.username)

    def set_active(self, user_id: int, active: bool, actor: str) -> None:
        if not active and self._is_last_active_admin(user_id):
            raise AuthError("Cannot deactivate the last active administrator.")
        self.db.execute("UPDATE users SET is_active = ? WHERE id = ?", (1 if active else 0, user_id))
        user = self.get_user(user_id)
        state = "activated" if active else "deactivated"
        self.audit.log(AuditCode.USER, f"{state} user {user.username if user else user_id}", actor)

    def set_role(self, user_id: int, role: str, actor: str) -> None:
        if role not in ROLES:
            raise AuthError(f"Unknown role '{role}'.")
        if role != "admin" and self._is_last_active_admin(user_id):
            raise AuthError("Cannot demote the last active administrator.")
        self.db.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
        user = self.get_user(user_id)
        self.audit.log(AuditCode.USER, f"role of {user.username if user else user_id} -> {role}", actor)

    def _is_last_active_admin(self, user_id: int) -> bool:
        row = self.db.fetchone(
            "SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND is_active = 1 AND id != ?",
            (user_id,),
        )
        target = self.get_user(user_id)
        return bool(target and target.is_admin and target.is_active and row and row["n"] == 0)
