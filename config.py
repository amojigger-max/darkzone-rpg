"""DarkZone v41 configuration. Credentials are only read from the environment."""
import os

VERSION = "41.1.1"
TOKEN = os.environ.get("BOT_TOKEN", "")
PAT = os.environ.get("PAT", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "8694290031"))
DB_PATH = os.environ.get("DZ_DB", "worldwar.db")
REPO = os.environ.get("DZ_REPO", "amojigger-max/darkzone-rpg")
STATE_BRANCH = os.environ.get("DZ_STATE_BRANCH", "main")
PRIMARY_GAME = int(os.environ.get("DZ_PRIMARY_GAME", "-1003614742240"))
BACKUP_DIR = os.environ.get("DZ_BACKUP_DIR", "backups")
STICKER_SET = os.environ.get("DZ_STICKER_SET", "darkzone_arsenal_by_REDarkZoneBot")
K = "━" * 18
