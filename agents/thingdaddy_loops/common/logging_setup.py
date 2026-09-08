"""logging_setup.py — rotating file logs + console, shared by both loops."""
import logging, os
from logging.handlers import RotatingFileHandler

def setup(log_dir="logs", name="thingdaddy", level="INFO"):
    os.makedirs(log_dir, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    for h in list(root.handlers):
        root.removeHandler(h)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    fh = RotatingFileHandler(os.path.join(log_dir, f"{name}.log"),
                             maxBytes=5_000_000, backupCount=5)
    fh.setFormatter(fmt)
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    root.addHandler(fh)
    root.addHandler(ch)
    return logging.getLogger(name)
