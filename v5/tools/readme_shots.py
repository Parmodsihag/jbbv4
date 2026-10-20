"""Screenshots for the repository README: a made-up demo shop in a throwaway database.

python tools/readme_shots.py                  # every shot -> ../docs/screenshots
python tools/readme_shots.py counter today    # only these

Windows only (PrintWindow through pywin32).  The window is drawn at 100% - 1366x745 inside,
as the shop's 1366x768 PC shows it - whatever this PC's own scaling is.  Names, phones and
amounts are invented; the real data folder is never opened.
"""

from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

V5 = Path(__file__).resolve().parent.parent
OUT = V5.parent / "docs" / "screenshots"
W, H = 1366, 745
SHOTS = (
    "today",
    "counter",
    "khata",
    "collections",
    "stock",
    "money",
    "reports",
    "settings",
    "assistant",
    "counter-hindi",
    "today-dark",
    "khata-dark",
    "classic-dashboard",
    "classic-sales",
)


# The demo shop ------------------------------------------------------------------------
def demo_shop(db) -> tuple[dict, dict]:
    """Twelve customers, eight items, six months of sales, payments, promises, a crop and
    a cash book.  Returns (customer ids, items) by name."""
    from hth.modules.crop_trading.service import CropService
    from hth.services.accounts import AccountsService
    from hth.services.company import CompanyService
    from hth.services.inventory import InventoryService
    from hth.services.krar import KrarService
    from hth.services.sales import SalesService, money_flow_handler

    CompanyService(db).update(phone="90000 00000", gstin="06XXXXX0000X1Z0")
    today = dt.date.today()

    def ago(days: int) -> str:
        return (today - dt.timedelta(days=days)).isoformat()

    acc, inv, sales, krar = AccountsService(db), InventoryService(db), SalesService(db), KrarService(db)
    people = {}
    for name, details in [
        ("RAMESH KUMAR", "S/O DHARAM SINGH KHARKHODA 9800000001"),
        ("SURESH PAL", "SAMPLA 9800000002"),
        ("BALWAN SINGH", "LAHLI 9800000003"),
        ("KRISHAN DALAL", "ROHTAK"),
        ("RAJBIR MALIK", "KHARKHODA 9800000005"),
        ("SATBIR HOODA", "SAMPLA 9800000006"),
        ("OM PRAKASH", "DHANSU"),
        ("JAGDISH RATHEE", "LAHLI 9800000008"),
        ("MAHAVIR SANGWAN", "ROHTAK"),
        ("SUNIL KADIAN", "ROHTAK"),
        ("DINESH JAKHAR", "SAMPLA 9800000011"),
        ("PAWAN NAIN", "KHARKHODA 9800000012"),
    ]:
        people[name] = acc.add_customer(name, details, 0, ago(200)).id

    stock = {}
    for name, cost, price, unit, qty, kind, gst, expiry in [
        ("UREA 45KG", 255, 266.5, "BAG", 200, "F", 5, "NA"),
        ("DAP 50KG", 1290, 1350, "BAG", 160, "F", 5, "NA"),
        ("SSP 50KG", 400, 420, "BAG", 72, "F", 5, "NA"),
        ("ZINC 33% 5KG", 80, 95, "BAG", 30, "F", 5, "NA"),
        ("WHEAT SEED HD-3086", 42, 48, "KG", 900, "S", 0, "NA"),
        ("MUSTARD SEED RH-725", 480, 520, "KG", 60, "S", 0, "NA"),
        ("GLYPHOSATE 1L", 410, 438, "BTL", 60, "P", 18, "NA"),
        ("CHLORPYRIFOS 20% 1L", 360, 395, "BTL", 12, "P", 18, ago(-11)),
    ]:
        stock[name] = inv.add_item(
            name, cost, price, unit, "NA", expiry, gst, kind, "P", ago(190), qty, "KISAN AGRO ROHTAK", "admin"
        )

    flow = money_flow_handler(db)
    cash = flow.money_accounts()[0]
    sbi = flow.add_account("SBI CURRENT", "bank", 150000, ago(60))
    flow.add_account("PHONEPE", "upi", 9000, ago(60))
    flow.owner(ago(30), cash.id, 20000, "in", "float")

    sold = {
        "RAMESH KUMAR": [
            ("WHEAT SEED HD-3086", 80, 185),
            ("UREA 45KG", 10, 171),
            ("DAP 50KG", 8, 83),
            ("UREA 45KG", 6, 67),
            ("WHEAT SEED HD-3086", 40, 53),
            ("GLYPHOSATE 1L", 2, 15),
            ("DAP 50KG", 2, 8),
        ],
        "BALWAN SINGH": [("DAP 50KG", 40, 120), ("UREA 45KG", 60, 110), ("SSP 50KG", 30, 95), ("DAP 50KG", 20, 2)],
        "SURESH PAL": [("UREA 45KG", 12, 30), ("ZINC 33% 5KG", 10, 25), ("DAP 50KG", 4, 0)],
        "SATBIR HOODA": [("DAP 50KG", 25, 190), ("UREA 45KG", 30, 186)],
        "RAJBIR MALIK": [("GLYPHOSATE 1L", 4, 20), ("ZINC 33% 5KG", 8, 18)],
        "JAGDISH RATHEE": [("DAP 50KG", 10, 0), ("MUSTARD SEED RH-725", 4, 40)],
        "SUNIL KADIAN": [("DAP 50KG", 30, 70), ("UREA 45KG", 40, 65)],
        "DINESH JAKHAR": [("UREA 45KG", 20, 60), ("ZINC 33% 5KG", 4, 50)],
        "PAWAN NAIN": [("DAP 50KG", 12, 45), ("WHEAT SEED HD-3086", 100, 40)],
        "OM PRAKASH": [("UREA 45KG", 4, 12)],
    }
    for who, rows in sold.items():
        for item, qty, days in rows:
            i = stock[item]
            sales.record(
                "P", ago(days), people[who], i.display, qty, i.last_value, "1", "emp1", item_id=i.id, unit=i.unit
            )
    for who, amount, days, account in [
        ("RAMESH KUMAR", 2000, 97, cash),
        ("RAMESH KUMAR", 5000, 48, cash),
        ("BALWAN SINGH", 20000, 60, sbi),
        ("SURESH PAL", 3000, 0, cash),
        ("OM PRAKASH", 1066, 0, cash),
        ("SUNIL KADIAN", 10000, 17, sbi),
        ("JAGDISH RATHEE", 2000, 0, cash),
    ]:
        sales.record("M", ago(days), people[who], "CASH", 1, amount, "1", "emp1", money_account_id=account.id)
    sales.record("M", ago(0), people["KRISHAN DALAL"], "PURCHASE ADVANCE", 1, 12800, "2", "admin")

    for who, days in [
        ("RAMESH KUMAR", 3),
        ("SATBIR HOODA", 9),
        ("SUNIL KADIAN", 5),
        ("DINESH JAKHAR", 7),
        ("PAWAN NAIN", 1),
        ("BALWAN SINGH", 0),
        ("RAJBIR MALIK", 0),
        ("JAGDISH RATHEE", -6),
    ]:
        krar.add_or_update(people[who], ago(days + 20))
        krar.add_or_update(people[who], ago(days))

    # crops: a farmer sells wheat in three lots, a buyer takes some
    wheat = CropService(db).add_crop("WHEAT", "KG")
    for days, gross, rate in [(40, 4250, 23.8), (25, 3100, 24.4), (12, 2200, 24.6)]:
        sales.record(
            "M",
            ago(days),
            people["MAHAVIR SANGWAN"],
            wheat.display,
            gross,
            rate,
            "2",
            "admin",
            item_id=wheat.id,
            unit="KG",
            deduction=50,
            quality="A",
            notes="tractor",
        )
    sales.record(
        "P", ago(5), people["KRISHAN DALAL"], wheat.display, 3000, 25.1, "2", "admin", item_id=wheat.id, unit="KG"
    )

    heads = {h.name: h.id for h in flow.heads("expense")}
    office = next(v for k, v in heads.items() if k.startswith("OFFICE"))
    flow.add_expense(ago(0), cash.id, office, 240, "tea and snacks")
    flow.add_expense(ago(6), cash.id, heads["ELECTRICITY"], 4350, "bill")
    flow.add_expense(ago(9), cash.id, heads["TRANSPORT"], 1800, "DAP from Rohtak")
    flow.transfer(ago(0), cash.id, sbi.id, 10000, "deposit")
    flow.add_recurring(heads["RENT"], cash.id, 12000, 1, "shop rent", start_month=today.strftime("%Y-%m"))
    return people, stock


# Capturing ----------------------------------------------------------------------------
def print_window(app):
    """The window's own pixels (PrintWindow), whatever is on top of it on the screen."""
    import win32gui
    import win32ui
    from PIL import Image

    hwnd = int(app.wm_frame(), 16)
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    w, h = right - left, bottom - top
    if w <= 0 or h <= 0:
        return None
    wdc = win32gui.GetWindowDC(hwnd)
    mdc = win32ui.CreateDCFromHandle(wdc)
    sdc = mdc.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(mdc, w, h)
    sdc.SelectObject(bmp)
    ok = ctypes.windll.user32.PrintWindow(hwnd, sdc.GetSafeHdc(), 3)  # client area, full content
    info = bmp.GetInfo()
    bits = bmp.GetBitmapBits(True)
    raw = {32: "BGRX", 24: "BGR"}.get(info["bmBitsPixel"])
    img = None
    if ok and raw and len(bits) >= info["bmWidthBytes"] * info["bmHeight"]:
        img = Image.frombuffer("RGB", (info["bmWidth"], info["bmHeight"]), bits, "raw", raw, info["bmWidthBytes"], 1)
    win32gui.DeleteObject(bmp.GetHandle())
    sdc.DeleteDC()
    mdc.DeleteDC()
    win32gui.ReleaseDC(hwnd, wdc)
    return img


def blank(img) -> bool:
    lo, hi = img.convert("L").getextrema()
    return hi - lo < 10


# Polishing ----------------------------------------------------------------------------
RADIUS, SS = 12, 4  # corner radius, supersampling for smooth edges


def rounded(img):
    """Rounded corners and a hairline border, on a transparent background."""
    from PIL import Image, ImageChops, ImageDraw

    w, h = img.size
    big = Image.new("L", (w * SS, h * SS), 0)
    ImageDraw.Draw(big).rounded_rectangle((0, 0, w * SS - 1, h * SS - 1), RADIUS * SS, fill=255)
    mask = big.resize((w, h), Image.LANCZOS)
    ring = Image.new("L", (w * SS, h * SS), 0)
    ImageDraw.Draw(ring).rounded_rectangle((0, 0, w * SS - 1, h * SS - 1), RADIUS * SS, outline=255, width=SS)
    ring = ImageChops.multiply(ring.resize((w, h), Image.LANCZOS), Image.new("L", (w, h), 150))
    rgba = Image.composite(Image.new("RGBA", (w, h), (140, 149, 159, 255)), img.convert("RGBA"), ring)
    rgba.putalpha(mask)
    return rgba


def hero(light, dark):
    """One screen, light on the left and dark on the right, split on a diagonal."""
    from PIL import Image, ImageDraw

    w, h = light.size
    top, bottom = round(w * 0.64), round(w * 0.46)
    big = Image.new("L", (w * SS, h * SS), 0)
    ImageDraw.Draw(big).polygon([(top * SS, 0), (w * SS, 0), (w * SS, h * SS), (bottom * SS, h * SS)], fill=255)
    img = Image.composite(dark.convert("RGB"), light.convert("RGB"), big.resize((w, h), Image.LANCZOS))
    line = Image.new("L", (w * SS, h * SS), 0)
    ImageDraw.Draw(line).line([(top * SS, 0), (bottom * SS, h * SS)], fill=255, width=3 * SS)
    return Image.composite(Image.new("RGB", (w, h), (34, 211, 238)), img, line.resize((w, h), Image.LANCZOS))


# The tour -----------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("only", nargs="*", help=f"take only these shots: {', '.join(SHOTS)}")
    parser.add_argument("--out", type=Path, default=OUT, help=f"where the images go (default {OUT})")
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("Windows only")
    only = set(args.only)
    if only - set(SHOTS):
        parser.error(f"no such shot: {', '.join(sorted(only - set(SHOTS)))}")
    args.out.mkdir(parents=True, exist_ok=True)

    data = Path(tempfile.mkdtemp(prefix="hth-readme-"))
    os.environ["HTH_DATA_DIR"] = str(data)
    os.environ["HTH_NO_UPDATE_CHECK"] = "1"
    sys.path.insert(0, str(V5))

    # Real pixels at 100%: without this, 150% Windows scaling makes the window bigger than
    # the screen, and its bottom edge comes out black.
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
    import customtkinter as ctk

    ctk.deactivate_automatic_dpi_awareness()

    from PIL import Image, ImageGrab

    import hth.assistant.voice as voice
    from hth.config import get_settings
    from hth.db.connection import Database
    from hth.db.schema import initialize
    from hth.services.auth import AuthService
    from hth.services.preferences import Preferences
    from hth.ui.views.setup import mark_setup

    voice.bundled_dir = lambda: data / "no-voice"  # no voice model to unpack for the demo
    settings = get_settings()
    db = Database(settings.db_path)
    initialize(db)
    AuthService(db).ensure_default_users()
    mark_setup(db, True)
    prefs = Preferences(db)
    prefs.set_layout("new")
    prefs.set_theme("light")
    prefs.set_language("en")
    people, stock = demo_shop(db)

    from hth.ui.app import App

    app = App(db, settings)
    app.tk.call("tk", "scaling", 96 / 72)  # point-sized table fonts as at 96 dpi
    raw: dict[str, Image.Image] = {}

    def pump(n=60, s=0.02):
        for _ in range(n):
            app.update()
            time.sleep(s)

    def wait_for(cond, seconds=20):
        end = time.time() + seconds
        while time.time() < end:
            app.update()
            if cond():
                return True
            time.sleep(0.05)
        return False

    def size():
        app.state("normal")  # also back from minimised, if something minimised it meanwhile
        app.geometry(f"{W}x{H}+0+0")
        pump(10)

    def tidy(status):
        """No temp-folder path on screen (it names the Windows user); a fresh status line."""
        stack = [app]
        while stack:
            w = stack.pop()
            stack.extend(w.winfo_children())
            if isinstance(w, ctk.CTkLabel) and str(data) in str(w.cget("text")):
                w.configure(text="demo data · hth.db")
        if status is not None:
            app.status_label.configure(text=status)

    def shot(name, status="Ready"):
        if only and name not in only:
            return
        size()
        tidy(status)
        img = None
        for _attempt in range(5):
            pump()
            img = print_window(app)
            if img is None or blank(img):
                x, y, w, h = app.winfo_rootx(), app.winfo_rooty(), app.winfo_width(), app.winfo_height()
                img = ImageGrab.grab(bbox=(x, y, x + w, y + h)).convert("RGB")
            if not blank(img):
                break
            time.sleep(1)
        raw[name] = img
        rounded(img).save(args.out / f"{name}.png", optimize=True)
        print("shot", name, img.size, "BLANK" if blank(img) else "")

    def counter_sale():
        app.navigate("counter")
        view = app._views["counter"]
        view.set_intent("sale")
        view.pick_customer(people["RAMESH KUMAR"])
        view.item.refresh()
        for name, qty in (("UREA 45KG", "4"), ("DAP 50KG", "2"), ("WHEAT SEED HD-3086", "40")):
            view.item.set(stock[name].id)
            view._on_item(stock[name].id, focus=False)
            view.qty.set(qty)
            view.add_line()
        view.paid.delete(0, "end")
        view.paid.insert(0, "2000")
        view.recalc()

    try:
        size()
        app.attributes("-topmost", True)  # stay in front while the tour runs
        app._login.username.set("admin")
        app._login.password.set("admin")
        app._login.submit()
        pump(30)

        today = app._views["today"]
        wait_for(lambda: today._data is not None)
        shot("today")

        counter_sale()
        shot("counter", status=None)  # its status line says what was picked

        app.navigate("customers", customer_id=people["RAMESH KUMAR"])
        page = app._views["khata"].customers
        wait_for(lambda: len(page.table.rows) > 5)
        page.page.period.set("All")
        page.page._apply_period()
        shot("khata")

        app.navigate("karar")
        app._views["khata"].collections.table.select_first()
        shot("collections")

        app.navigate("items", item_id=stock["DAP 50KG"].id)
        items = app._views["stock"].items
        wait_for(lambda: len(items.table.rows) > 5)
        shot("stock")

        app.navigate("finance")
        book = app._views["money"].book
        book.period.set("This month")
        book.reload()
        shot("money")

        app.navigate("reports")
        shot("reports")

        app.navigate("settings")
        shot("settings")

        if not only or "assistant" in only:
            app.navigate("assistant")
            assistant = app.find_view("assistant")
            # System 1 trains itself the first time the screen opens: give it time
            if wait_for(lambda: getattr(assistant, "_ready", False), 180):
                assistant.new_chat()
                pump(20)
                assistant.ask("sabse bade 5 bakayedar")
                wait_for(lambda: not getattr(assistant, "_busy", False), 60)
                shot("assistant")

        app.apply_language("hi")
        pump(30)
        counter_sale()
        shot("counter-hindi", status=None)
        app.apply_language("en")
        pump(30)

        app.apply_theme("dark")
        app.navigate("today")
        today = app._views["today"]
        today.reload()
        wait_for(lambda: today._data is not None)
        pump(40)
        shot("today-dark")
        app.navigate("customers", customer_id=people["BALWAN SINGH"])
        page = app._views["khata"].customers
        wait_for(lambda: len(page.table.rows) > 5)
        shot("khata-dark")
        app.apply_theme("light")
        pump(20)

        app.apply_layout("classic")
        pump(30)
        app.navigate("dashboard")
        dash = app._views["dashboard"]
        wait_for(lambda: dash._data is not None)
        pump(80)
        shot("classic-dashboard")
        app.navigate("sales")
        pump(30)
        shot("classic-sales")
        app.apply_layout("new")
        pump(20)
    finally:
        app.destroy()
        shutil.rmtree(data, ignore_errors=True)

    if "today" in raw and "today-dark" in raw:
        rounded(hero(raw["today"], raw["today-dark"])).save(args.out / "hero.png", optimize=True)
        print("hero", raw["today"].size)
    bad = [n for n, img in raw.items() if blank(img)]
    print(f"{len(raw)} shots in {args.out}" + (f" - BLANK: {', '.join(bad)}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
