import os
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────────────────────
# Instagram iOS client constants (reversed from v259.0.0.27.98)
# ──────────────────────────────────────────────────────────────
IG_APP_ID          = "567067343352427"
IG_APP_VERSION     = "259.0.0.27.98"
IG_VERSION_CODE    = "405398279"
IG_SIG_KEY         = "4f8732eb9ba7d032fb6b7b15c3c0c5f6e6e4ef4d"
IG_SIG_KEY_VERSION = "4"
IG_CAPABILITIES    = "3brTBw=="
IG_API_URL         = "https://i.instagram.com/api/v1"
IG_CDN_URL         = "https://rupload.instagram.com/mime_type_production"

# ──────────────────────────────────────────────────────────────
# TikTok iOS client constants (reversed from v26.1.0)
# ──────────────────────────────────────────────────────────────
TT_APP_ID          = "1233"
TT_APP_VERSION     = "26.1.0"
TT_APP_BUILD       = "261018"
TT_API_DOMAIN      = "api16-normal-c-useast1a.tiktokv.com"
TT_API_URL         = f"https://{TT_API_DOMAIN}"
TT_GORGON_SALT     = bytes.fromhex("6b657973616c7465642e736b5f7461696c")

# ──────────────────────────────────────────────────────────────
# Twitter/X iOS client constants (reversed from Twitter 9.x)
# ──────────────────────────────────────────────────────────────
TW_CONSUMER_KEY    = "IQKbtAYlXLripLGFWd8pajn4A"
TW_CONSUMER_SECRET = "LBF8XLBEtBpyCHWmwiqkrCMnVYqRR8XiYxYS6Kxe0"
TW_API_URL         = "https://api.twitter.com"
TW_UPLOAD_URL      = "https://upload.twitter.com"
TW_BEARER_TOKEN    = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
    "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)

# ──────────────────────────────────────────────────────────────
# Reddit iOS client constants (reversed from Reddit 2023.x)
# ──────────────────────────────────────────────────────────────
RD_CLIENT_ID   = "LNDo9tips78yg"
RD_API_URL     = "https://oauth.reddit.com"
RD_AUTH_URL    = "https://www.reddit.com/api/v1"
RD_APP_VERSION = "2023.32.0"

# ──────────────────────────────────────────────────────────────
# Runtime credentials (populated from .env / environment)
# ──────────────────────────────────────────────────────────────
ACCOUNTS = {
    "instagram": {
        "username": os.getenv("IG_USERNAME", ""),
        "password": os.getenv("IG_PASSWORD", ""),
    },
    "tiktok": {
        "username": os.getenv("TT_USERNAME", ""),
        "password": os.getenv("TT_PASSWORD", ""),
    },
    "twitter": {
        "username":      os.getenv("TW_USERNAME", ""),
        "password":      os.getenv("TW_PASSWORD", ""),
        "access_token":  os.getenv("TW_ACCESS_TOKEN", ""),
        "access_secret": os.getenv("TW_ACCESS_SECRET", ""),
    },
    "reddit": {
        "username": os.getenv("RD_USERNAME", ""),
        "password": os.getenv("RD_PASSWORD", ""),
    },
}

# ──────────────────────────────────────────────────────────────
# Proxy config (optional)
# ──────────────────────────────────────────────────────────────
PROXY_LIST_PATH = os.getenv("PROXY_LIST", "proxies.txt")
USE_PROXY       = os.getenv("USE_PROXY", "false").lower() == "true"

# ──────────────────────────────────────────────────────────────
# AutoUpload scheduler defaults
# ──────────────────────────────────────────────────────────────
UPLOAD_INTERVAL_MINUTES = int(os.getenv("UPLOAD_INTERVAL", "60"))
CONTENT_DIR             = os.getenv("CONTENT_DIR", "content/")

# ──────────────────────────────────────────────────────────────
# AutoReg defaults
# ──────────────────────────────────────────────────────────────
REG_COUNT     = int(os.getenv("REG_COUNT", "1"))
EMAIL_DOMAIN  = os.getenv("EMAIL_DOMAIN", "guerrillamail.com")

# ──────────────────────────────────────────────────────────────
# AutoDM defaults
# ──────────────────────────────────────────────────────────────
DM_DELAY_SECONDS = int(os.getenv("DM_DELAY", "5"))
DM_TARGET_FILE   = os.getenv("DM_TARGETS", "targets.txt")
DM_MESSAGE_FILE  = os.getenv("DM_MESSAGES", "messages.txt")
