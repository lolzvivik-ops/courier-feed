#!/usr/bin/env python3
"""
social_ios_automation — CLI entry point

Usage examples:
  python main.py login   --platform ig  --username alice --password s3cr3t
  python main.py upload  --platform all --file content/
  python main.py reg     --platform ig,tt --count 5
  python main.py dm      --platform ig   --targets targets.txt --messages messages.txt
  python main.py dm-one  --platform ig   --to alex_123 --message "Hey there"
  python main.py device  --action new --save devices/alice.json
"""

import argparse
import json
import logging
import os
import sys
from typing import Dict, Any, Optional

from colorama import Fore, Style, init as colorama_init

# ── relative imports work when run from this directory ──────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from social_ios_automation.core.device   import DeviceProfile
from social_ios_automation.core.session  import PlatformSession
from social_ios_automation.platforms.instagram import InstagramClient
from social_ios_automation.platforms.tiktok    import TikTokClient
from social_ios_automation.platforms.twitter   import TwitterClient
from social_ios_automation.platforms.reddit    import RedditClient
from social_ios_automation.features.autoupload import AutoUploader
from social_ios_automation.features.autoreg    import AutoRegistrar
from social_ios_automation.features.autodm     import AutoDM
from social_ios_automation.utils.proxy         import ProxyPool
import social_ios_automation.config as config

colorama_init(autoreset=True)

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt = "%H:%M:%S",
)
logger = logging.getLogger("main")


# ── platform builder ──────────────────────────────────────────────────────────

def build_client(
    platform:     str,
    device_file:  Optional[str] = None,
    session_file: Optional[str] = None,
    proxy_url:    Optional[str] = None,
) -> Any:
    if device_file and os.path.exists(device_file):
        device = DeviceProfile.from_file(device_file)
    else:
        device = DeviceProfile.random()

    sess = session_file or f".session_{platform}.json"

    MAP = {
        "ig": InstagramClient,
        "tt": TikTokClient,
        "tw": TwitterClient,
        "rd": RedditClient,
    }
    cls = MAP.get(platform)
    if not cls:
        raise ValueError(f"Unknown platform: {platform}")
    return cls(device=device, proxy_url=proxy_url, session_file=sess)


def build_all_clients(
    platforms: list,
    proxy_pool: Optional[ProxyPool] = None,
) -> Dict[str, Any]:
    clients = {}
    for p in platforms:
        proxy = proxy_pool.next() if proxy_pool else None
        try:
            clients[p] = build_client(p, proxy_url=proxy)
        except Exception as e:
            logger.warning("Could not build client for %s: %s", p, e)
    return clients


# ── sub-command handlers ──────────────────────────────────────────────────────

def cmd_login(args) -> None:
    """Login and persist session."""
    p = args.platform.lower()
    client = build_client(p, device_file=args.device, proxy_url=args.proxy)

    if p == "ig":
        result = client.login(args.username, args.password)
    elif p == "tt":
        client.register_device()
        result = client.login(args.username, args.password)
    elif p == "tw":
        result = client.login(args.username, args.password)
    elif p == "rd":
        result = client.login(args.username, args.password)
    else:
        print(Fore.RED + f"Unknown platform: {p}")
        return

    ok = result.get("status") == "ok" or "access_token" in result or "logged_in_user" in result
    color = Fore.GREEN if ok else Fore.RED
    print(color + json.dumps(result, indent=2)[:400])
    if ok:
        print(Fore.GREEN + f"\n[+] Session saved to .session_{p}.json")


def cmd_upload(args) -> None:
    """Upload content from a directory."""
    platforms_str = args.platform.lower()
    if platforms_str == "all":
        plats = ["ig", "tt", "tw", "rd"]
    else:
        plats = [p.strip() for p in platforms_str.split(",")]

    proxy_pool = ProxyPool(proxy_file=args.proxies) if args.proxies else None
    clients    = build_all_clients(plats, proxy_pool)

    uploader = AutoUploader(
        clients         = clients,
        content_dir     = args.file or config.CONTENT_DIR,
        interval_minutes= args.interval,
        posted_log      = ".posted.json",
    )

    if args.loop:
        print(Fore.CYAN + f"[*] Running upload loop every {args.interval} min …")
        uploader.run()
    else:
        result = uploader.upload_next()
        print(Fore.GREEN + json.dumps(result, indent=2, default=str) if result
              else Fore.YELLOW + "No pending content found.")


def cmd_reg(args) -> None:
    """Bulk register accounts."""
    platforms = [p.strip() for p in args.platform.split(",")]
    proxy_pool = ProxyPool(proxy_file=args.proxies) if args.proxies else None

    reg = AutoRegistrar(
        platforms      = platforms,
        proxy_pool     = proxy_pool,
        count          = args.count,
        output_file    = args.output or "accounts.json",
        use_temp_mail  = not args.no_tempmail,
        delay_between  = args.delay,
    )
    accounts = reg.run()
    print(Fore.GREEN + f"[+] Created {len(accounts)} accounts → {reg._output}")


def cmd_dm(args) -> None:
    """Bulk DM from target file."""
    platforms_str = args.platform.lower()
    if platforms_str == "all":
        plats = ["ig", "tt", "tw", "rd"]
    else:
        plats = [p.strip() for p in platforms_str.split(",")]

    proxy_pool = ProxyPool(proxy_file=args.proxies) if args.proxies else None
    clients    = build_all_clients(plats, proxy_pool)

    dm = AutoDM(
        clients         = clients,
        target_file     = args.targets or config.DM_TARGET_FILE,
        message_file    = args.messages or config.DM_MESSAGE_FILE,
        delay_seconds   = args.delay,
        max_per_session = args.max,
    )
    stats = dm.run()
    print(Fore.GREEN + f"[+] DM stats: {stats}")


def cmd_dm_one(args) -> None:
    """Send a single DM."""
    p = args.platform.lower()
    client = build_client(p, proxy_url=args.proxy)
    dm = AutoDM(clients={p: client})
    result = dm.send_one(
        platform   = p,
        identifier = args.to,
        message    = args.message,
        subject    = args.subject or "",
    )
    color = Fore.GREEN if result.get("ok") else Fore.RED
    print(color + json.dumps(result, indent=2, default=str))


def cmd_device(args) -> None:
    """Generate or inspect a device profile."""
    if args.action == "new":
        dev = DeviceProfile.random()
        if args.save:
            dev.save(args.save)
            print(Fore.GREEN + f"[+] Device saved → {args.save}")
        print(json.dumps(dev.__dict__, indent=2))
    elif args.action == "show" and args.save:
        dev = DeviceProfile.from_file(args.save)
        print(json.dumps(dev.__dict__, indent=2))
    else:
        print(Fore.RED + "Specify --action new [--save path] or --action show --save path")


# ── argument parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog        = "social_ios_automation",
        description = "iOS mobile API automation for Instagram / TikTok / X / Reddit",
        formatter_class = argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="command", required=True)

    # ── login ────────────────────────────────────────────────────────────────
    login_p = sub.add_parser("login", help="Authenticate and save session")
    login_p.add_argument("--platform",  required=True, choices=["ig","tt","tw","rd"])
    login_p.add_argument("--username",  required=True)
    login_p.add_argument("--password",  required=True)
    login_p.add_argument("--device",    help="Path to device .json file")
    login_p.add_argument("--proxy",     help="Proxy URL")

    # ── upload ───────────────────────────────────────────────────────────────
    up_p = sub.add_parser("upload", help="Auto-upload content")
    up_p.add_argument("--platform",  default="all", help="Comma-separated: ig,tt,tw,rd or 'all'")
    up_p.add_argument("--file",      help="Content directory")
    up_p.add_argument("--interval",  type=int, default=60, help="Loop interval (minutes)")
    up_p.add_argument("--proxies",   help="Proxy list file")
    up_p.add_argument("--loop",      action="store_true", help="Run continuously")

    # ── reg ──────────────────────────────────────────────────────────────────
    reg_p = sub.add_parser("reg", help="Auto-register accounts")
    reg_p.add_argument("--platform",     default="ig,tt,tw,rd")
    reg_p.add_argument("--count",        type=int, default=1)
    reg_p.add_argument("--output",       help="Output JSONL file")
    reg_p.add_argument("--proxies",      help="Proxy list file")
    reg_p.add_argument("--delay",        type=float, default=5.0)
    reg_p.add_argument("--no-tempmail",  action="store_true")

    # ── dm ───────────────────────────────────────────────────────────────────
    dm_p = sub.add_parser("dm", help="Bulk DM from target file")
    dm_p.add_argument("--platform",  default="all")
    dm_p.add_argument("--targets",   help="Target list file")
    dm_p.add_argument("--messages",  help="Message template file")
    dm_p.add_argument("--delay",     type=float, default=8.0)
    dm_p.add_argument("--max",       type=int, default=200)
    dm_p.add_argument("--proxies",   help="Proxy list file")

    # ── dm-one ───────────────────────────────────────────────────────────────
    dmo_p = sub.add_parser("dm-one", help="Send a single DM")
    dmo_p.add_argument("--platform", required=True, choices=["ig","tt","tw","rd"])
    dmo_p.add_argument("--to",       required=True, help="Target username or user_id")
    dmo_p.add_argument("--message",  required=True)
    dmo_p.add_argument("--subject",  help="Subject (Reddit only)")
    dmo_p.add_argument("--proxy",    help="Proxy URL")

    # ── device ───────────────────────────────────────────────────────────────
    dev_p = sub.add_parser("device", help="Manage device profiles")
    dev_p.add_argument("--action", required=True, choices=["new","show"])
    dev_p.add_argument("--save",   help="Path to read/write device JSON")

    return p


def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    dispatch = {
        "login":  cmd_login,
        "upload": cmd_upload,
        "reg":    cmd_reg,
        "dm":     cmd_dm,
        "dm-one": cmd_dm_one,
        "device": cmd_device,
    }
    handler = dispatch.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
