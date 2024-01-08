#!/usr/bin/env python

import sys
from pathlib import Path

from neosca.ns_about import __version__

PKG_DIR: Path = Path(__file__).parent.absolute()
# https://stackoverflow.com/a/13790741/20732031
attr = "_MEIPASS"
if hasattr(sys, attr):
    NEOSCA_DIR: Path = Path(getattr(sys, attr)).absolute()
else:
    NEOSCA_DIR: Path = PKG_DIR.parent.parent

DATA_DIR: Path = PKG_DIR / "ns_data"
QSS_PATH: Path = DATA_DIR / "styles.qss"
STANZA_MODEL_DIR: Path = DATA_DIR / "stanza_resources"
CITING_PATH: Path = DATA_DIR / "citings.json"
ACKS_PATH: Path = DATA_DIR / "acks.json"
ICON_PATH: Path = DATA_DIR / "ns_icon.ico"
ICON_MAC_PATH: Path = DATA_DIR / "ns_icon.icns"
SETTING_PATH: Path = DATA_DIR / "settings.ini"

DESKTOP_PATH: Path = Path.home().absolute() / "Desktop"

sys.path.insert(0, str(PKG_DIR))

__all__ = ["__version__"]
