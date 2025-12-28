"""
SEKAM2 Configファイル
"""

import os
import re

from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("token")
SENKATOKEN = os.getenv("SENKATOKEN")

DB_HOST = os.getenv("dbhost")
DB_USER = os.getenv("dbuser")
DB_PASSWORD = os.getenv("dbpassword")
DB_NAME = os.getenv("dbname")

STAT_DB_HOST = os.getenv("statdbhost")
STAT_DB_USER = os.getenv("statdbuser")
STAT_DB_PASSWORD = os.getenv("statdbpassword")
STAT_DB_NAME = os.getenv("statdbname")

debug = True

OVERLOAD_MODE = False
ALLOWED_GUILD_ID = 518371205452005387

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")

REFERENCE_DATA_DEFAULT_LABEL = "-# 参照データ:更新日不明"

SPECIAL_OK = {
    "__",
    "bi",
    "e_",
    "ebi",
    "ebisushi",
    "kanji",
    "mo",
    "pineappleman",
    "ebing",
}

TONE_SUFFIX_RE = re.compile(
    r"_(?:tone[1-5]|light_skin_tone|medium_light_skin_tone|medium_skin_tone|"
    r"medium_dark_skin_tone|dark_skin_tone)$"
)

_CUSTOM_EMOJI_RE = re.compile(r"^<:([A-Za-z0-9_]+):\d+>$")

EMOJI_JSON_PATH = os.path.join(os.path.dirname(__file__), "discord-emojis.pretty.json")

REWIND_TOKEN_JSON_PATH = os.getenv("REWIND_TOKEN_JSON_PATH")

REWIND_VIDEO_DIR = os.getenv("REWIND_VIDEO_DIR")

REWIND_BASE_URL = os.getenv("REWIND_BASE_URL")

REWIND_NOTIFY_WEBHOOK_URL = os.getenv("REWIND_NOTIFY_WEBHOOK_URL")
