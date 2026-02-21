import sys
import os

def get_base_dir():
    if getattr(sys, "frozen", False):
        BASE_DIR = os.path.dirname(sys.executable)
    else:
        BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
    return BASE_DIR