"""Load the model library and its installed Runtime dependency."""

from ctypes import CDLL
from functools import lru_cache
from pathlib import Path

from pandora_runtime import load_library


@lru_cache(maxsize=1)
def library():
    package = Path(__file__).resolve().parent
    installed = package / "lib" / "libqwen25_omni.so"
    source = package.parent.parent / "lib" / installed.name
    load_library()
    return CDLL(str(installed if installed.is_file() else source))
