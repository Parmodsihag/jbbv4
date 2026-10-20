"""Convenience launcher: ``python run.py``."""

from hth.__main__ import main

if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()  # the packaged app starts the assistant's model process from itself
    raise SystemExit(main())
