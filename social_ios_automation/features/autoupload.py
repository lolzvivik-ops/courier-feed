"""
AutoUploader — scheduled content distribution engine.

Watches a content directory for media files + metadata JSON sidecar,
then publishes them across all configured platform clients on a schedule.

Content directory layout:
  content/
    001_beach.jpg              ← image
    001_beach.json             ← {"caption":"...", "platforms":["ig","tt","tw","rd"],
                                   "hashtags":["nature"], "subreddit":"pics",
                                   "title":"Beach vibes", "post_at":"2024-01-01T12:00:00"}
    002_video.mp4
    002_video_thumb.jpg
    002_video.json

Sidecar schema (all fields optional except caption/title):
  caption    — text caption (IG, TikTok, Reddit self-post body)
  title      — Reddit / X post title
  hashtags   — list of strings (no # prefix)
  platforms  — ["ig", "tt", "tw", "rd"] — defaults to all
  post_at    — ISO 8601 datetime; if absent, posts immediately
  subreddit  — Reddit subreddit (no r/)
  story      — bool, post as IG story instead of feed
  nsfw       — bool

Usage:
    from platforms import InstagramClient, TikTokClient, TwitterClient, RedditClient
    from core     import DeviceProfile

    clients = {
        "ig": InstagramClient(DeviceProfile.random()),
        "tt": TikTokClient(DeviceProfile.random()),
        "tw": TwitterClient(DeviceProfile.random()),
        "rd": RedditClient(DeviceProfile.random()),
    }
    uploader = AutoUploader(clients, content_dir="content/", interval_minutes=60)
    uploader.run()          # blocking loop
    # or: uploader.upload_next()  for single-shot
"""

import json
import os
import time
import glob
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AutoUploader:
    """
    Scans content/ for pending posts and uploads them.

    upload_next() processes the oldest unposted item.
    run()         loops with interval_minutes between passes.
    """

    def __init__(
        self,
        clients:          Dict[str, Any],
        content_dir:      str   = "content/",
        interval_minutes: int   = 60,
        posted_log:       str   = ".posted.json",
    ):
        self._clients     = clients
        self._content_dir = content_dir.rstrip("/") + "/"
        self._interval    = interval_minutes * 60
        self._log_path    = posted_log
        self._posted:     set = set()
        self._lock        = threading.Lock()

        os.makedirs(self._content_dir, exist_ok=True)
        self._load_posted_log()

    # ── public API ────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Blocking upload loop. Call in a thread for non-blocking use."""
        logger.info("AutoUploader started — interval %d min", self._interval // 60)
        while True:
            try:
                self.upload_all_due()
            except Exception as exc:
                logger.exception("AutoUploader cycle error: %s", exc)
            time.sleep(self._interval)

    def upload_all_due(self) -> List[Dict[str, Any]]:
        """Upload every pending post whose post_at <= now."""
        results = []
        for meta_path in self._find_pending_meta():
            meta = self._load_meta(meta_path)
            if not meta:
                continue
            post_at = meta.get("post_at")
            if post_at:
                dt = datetime.fromisoformat(post_at).replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) < dt:
                    continue    # scheduled for later
            results.append(self.upload_item(meta_path, meta))
        return results

    def upload_next(self) -> Optional[Dict[str, Any]]:
        """Upload the single oldest pending item (ignores post_at schedule)."""
        pending = self._find_pending_meta()
        if not pending:
            logger.info("No pending content found.")
            return None
        meta_path = pending[0]
        meta      = self._load_meta(meta_path)
        return self.upload_item(meta_path, meta) if meta else None

    def upload_item(self, meta_path: str, meta: Dict[str, Any]) -> Dict[str, Any]:
        """Upload a single content item to its target platforms."""
        stem = meta_path.replace(".json", "")
        platforms = meta.get("platforms", list(self._clients.keys()))
        results   = {"meta": meta_path, "platforms": {}}

        media_path  = _find_media(stem)
        thumb_path  = _find_thumb(stem)
        is_video    = media_path and media_path.lower().endswith((".mp4", ".mov"))
        is_image    = media_path and not is_video

        caption   = meta.get("caption", "")
        title     = meta.get("title", caption[:100])
        hashtags  = meta.get("hashtags", [])
        subreddit = meta.get("subreddit", "test")
        story_mode= meta.get("story", False)
        nsfw      = meta.get("nsfw", False)

        for platform in platforms:
            client = self._clients.get(platform)
            if not client:
                logger.warning("No client for platform '%s'", platform)
                results["platforms"][platform] = {"error": "no client"}
                continue
            try:
                if platform == "ig":
                    r = self._upload_ig(client, media_path, caption, story_mode, is_video, thumb_path)
                elif platform == "tt":
                    r = self._upload_tt(client, media_path, caption, hashtags, is_video)
                elif platform == "tw":
                    r = self._upload_tw(client, media_path, title or caption, is_video or is_image)
                elif platform == "rd":
                    r = self._upload_rd(client, media_path, subreddit, title, caption,
                                        is_video, is_image, thumb_path, nsfw)
                else:
                    r = {"error": f"unknown platform {platform}"}
                results["platforms"][platform] = r
                logger.info("[%s] Upload result: %s", platform, r.get("status", r))
            except Exception as exc:
                logger.exception("[%s] Upload failed: %s", platform, exc)
                results["platforms"][platform] = {"error": str(exc)}

        self._mark_posted(meta_path)
        return results

    # ── platform-specific wrappers ────────────────────────────────────────────

    @staticmethod
    def _upload_ig(client, media_path, caption, story, is_video, thumb):
        if story:
            return client.upload_story(media_path)
        if is_video:
            return client.upload_video(media_path, thumb or media_path, caption)
        return client.upload_photo(media_path, caption)

    @staticmethod
    def _upload_tt(client, media_path, caption, hashtags, is_video):
        if not is_video:
            return {"error": "TikTok only supports video uploads"}
        return client.upload_video(media_path, caption=caption, hashtags=hashtags)

    @staticmethod
    def _upload_tw(client, media_path, text, has_media):
        if has_media and media_path:
            return client.post_with_media(text, media_path)
        return client.post_tweet(text)

    @staticmethod
    def _upload_rd(client, media_path, subreddit, title, text, is_video, is_image, thumb, nsfw):
        if is_image:
            return client.submit_image_post(subreddit, title, media_path)
        if is_video:
            return client.submit_video_post(subreddit, title, media_path, thumb or media_path)
        return client.submit_post(subreddit=subreddit, title=title, text=text, nsfw=nsfw)

    # ── internal ──────────────────────────────────────────────────────────────

    def _find_pending_meta(self) -> List[str]:
        all_json = sorted(glob.glob(self._content_dir + "*.json"))
        with self._lock:
            return [p for p in all_json if p not in self._posted]

    def _load_meta(self, path: str) -> Optional[Dict]:
        try:
            with open(path) as fh:
                return json.load(fh)
        except Exception as e:
            logger.error("Failed to load %s: %s", path, e)
            return None

    def _mark_posted(self, path: str) -> None:
        with self._lock:
            self._posted.add(path)
        self._save_posted_log()

    def _load_posted_log(self) -> None:
        if os.path.exists(self._log_path):
            try:
                with open(self._log_path) as fh:
                    self._posted = set(json.load(fh))
            except Exception:
                self._posted = set()

    def _save_posted_log(self) -> None:
        with open(self._log_path, "w") as fh:
            json.dump(list(self._posted), fh)


# ── file helpers ──────────────────────────────────────────────────────────────

def _find_media(stem: str) -> Optional[str]:
    for ext in (".mp4", ".mov", ".jpg", ".jpeg", ".png", ".gif"):
        p = stem + ext
        if os.path.exists(p):
            return p
    return None


def _find_thumb(stem: str) -> Optional[str]:
    for suffix in ("_thumb", "_thumbnail", "_cover"):
        for ext in (".jpg", ".jpeg", ".png"):
            p = stem + suffix + ext
            if os.path.exists(p):
                return p
    return None
