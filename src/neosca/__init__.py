#!/usr/bin/env python

import sys
from pathlib import Path

NEOSCA_HOME: Path = Path(__file__).parent.absolute()
SETTING_PATH: Path = NEOSCA_HOME / "settings.ini"

DATA_DIR: Path = NEOSCA_HOME / "data"
IMG_DIR: Path = NEOSCA_DIR / "imgs"
ICON_PATH: Path = IMG_DIR / "ns_icon.ico"
ICON_MAC_PATH: Path = IMG_DIR / "ns_icon.icns"
QSS_PATH: Path = DATA_DIR / "ns_style.qss"
CITING_PATH: Path = DATA_DIR / "citing.json"
STANZA_MODEL_DIR: Path = DATA_DIR / "stanza_resources"

DESKTOP_PATH: Path = Path.home().absolute() / "Desktop"

sys.path.insert(0, str(NEOSCA_HOME))
