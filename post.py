"""
Threads auto-poster for @bylovemason.

Runs every hour on GitHub Actions. Each item in queue.json carries its own
"at" time (New York time by default, set in config.json). When that time has
passed, the item is published through Meta's official Threads API and moved
to posted.json. Items without an "at" time fall back to config post_times.

No extra packages needed: standard Python only.
"""

import json
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

API = os.environ.get("THREADS_API_BASE", "https://graph.threads.net/v1.0")
HERE = os.path.dirname(os.path.abspath(__file__))
QUEUE_FILE = os.path.join(HERE, "queue.json")
POSTED_FILE = os.path.join(HERE, "posted.json")
CONFIG_FILE = os.path.join(HERE, "config.json")
MAX_CHARS = 500


def load(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


MEDIA_BASE = os.environ.get(
    "MEDIA_BASE", "https://raw.githubusercontent.com/bylovemason/threads-autoposter/main/")


def api_get(path, params):
    req = urllib.request.Request(f"{API}/{path}?" + urllib.parse.urlencode(params))
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Threads API error {e.code}: {e.read().decode(errors='replace')}") from None


def wait_until_ready(container_id, token, limit=600):
    """Videos (and sometimes images) need processing before they can be published."""
    waited = 0
    while waited < limit:
        st = api_get(container_id, {"fields": "status,error_message", "access_token": token})
        if st.get("status") == "FINISHED":
            return
        if st.get("status") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Media processing failed: {st}")
        time.sleep(10)
        waited += 10
    raise RuntimeError("Media took too long to process.")


def api_post(path, params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{API}/{path}", data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"Threads API error {e.code}: {body}") from None


def due_slot(cfg, now, posted, today):
    """Return the earliest posting slot that is due and not yet posted today.

    A slot like '12:30' becomes due once the clock reaches its hour (12:xx).
    GitHub sometimes runs scheduled jobs late, so a missed slot can still be
    caught up for up to 3 hours. Older missed slots are skipped, so you never
    get a burst of posts at once.
    """
    done = {p.get("slot") for p in posted if p.get("date") == today}
    for slot in sorted(cfg["post_times"]):
        if slot in done:
            continue
        h, m = map(int, slot.split(":"))
        slot_hour = now.replace(hour=h, minute=0, second=0, microsecond=0)
        if slot_hour <= now < slot_hour + timedelta(hours=3):
            return slot
    return None


def main():
    cfg = load(CONFIG_FILE, None)
    if cfg is None:
        sys.exit("config.json is missing.")
    if cfg.get("paused"):
        print("Posting is paused in config.json. Nothing to do.")
        return

    tz = ZoneInfo(cfg["timezone"])
    now = datetime.now(tz)
    force = os.environ.get("FORCE_POST") == "1"

    today = now.strftime("%Y-%m-%d")
    posted = load(POSTED_FILE, [])
    queue = load(QUEUE_FILE, [])
    if not queue:
        print("Queue is empty. Add posts to queue.json.")
        return

    # Items with an "at" time ("YYYY-MM-DD HH:MM", in config timezone) post at
    # that exact time. Items without one fall back to the post_times slots.
    def at_time(it):
        if isinstance(it, dict) and it.get("at"):
            return datetime.strptime(it["at"], "%Y-%m-%d %H:%M").replace(tzinfo=tz)
        return None

    idx, slot = None, None
    if force:
        idx, slot = 0, "manual"
    else:
        due = [(at_time(it), i) for i, it in enumerate(queue) if at_time(it) and at_time(it) <= now]
        if due:
            # Earliest overdue item first. One item per run, so a missed hour
            # catches up gradually instead of bursting.
            t, idx = min(due)
            slot = queue[idx]["at"]
        else:
            undated = [i for i, it in enumerate(queue) if not at_time(it)]
            if undated:
                slot = due_slot(cfg, now, posted, today)
                idx = undated[0] if slot else None
    if idx is None:
        nxt = min((at_time(it) for it in queue if at_time(it)), default=None)
        print(f"{now:%Y-%m-%d %H:%M} {cfg['timezone']}: nothing due."
              + (f" Next post at {nxt:%Y-%m-%d %H:%M}." if nxt else ""))
        return

    token = os.environ.get("THREADS_TOKEN")
    if not token:
        sys.exit("THREADS_TOKEN secret is missing.")

    item = queue[idx]
    remaining = queue[:idx] + queue[idx + 1:]
    # A queue item is either a single post {"text": "..."} or a long-form
    # thread {"thread": ["hook post", "post 2", ..., "CTA post"]}.
    if isinstance(item, dict) and "thread" in item:
        parts = [str(p).strip() for p in item["thread"] if str(p).strip()]
    else:
        parts = [(item["text"] if isinstance(item, dict) else str(item)).strip()]

    too_long = [i + 1 for i, p in enumerate(parts) if len(p) > MAX_CHARS]
    if not parts or too_long:
        print(f"Skipping this item: post(s) {too_long} are over {MAX_CHARS} characters. Moved to posted.json as 'too_long'.")
        posted.append({"parts": parts, "status": "too_long", "date": today, "slot": slot})
        save(POSTED_FILE, posted)
        save(QUEUE_FILE, remaining)
        return

    # Small random delay so posts don't land at the exact same minute every day.
    if not force:
        delay = random.randint(0, int(cfg.get("max_random_delay_minutes", 5)) * 60)
        print(f"Waiting {delay // 60}m {delay % 60}s before posting.")
        time.sleep(delay)

    wait = int(os.environ.get("PUBLISH_WAIT_SECONDS", "30"))
    ids = []
    error = None
    for i, text in enumerate(parts):
        params = {"media_type": "TEXT", "text": text, "access_token": token}
        # Optional photo or video on the first post: {"image": "media/x.jpg"} or {"video": "media/x.mp4"}
        if i == 0 and isinstance(item, dict) and (item.get("image") or item.get("video")):
            if item.get("image"):
                params.update(media_type="IMAGE", image_url=MEDIA_BASE + item["image"])
            else:
                params.update(media_type="VIDEO", video_url=MEDIA_BASE + item["video"])
        if ids:
            params["reply_to_id"] = ids[-1]  # chain each part under the previous one
        try:
            container = api_post("me/threads", params)
            if params["media_type"] != "TEXT":
                wait_until_ready(container["id"], token)
            # Meta recommends waiting about 30 seconds before publishing.
            time.sleep(wait)
            result = api_post("me/threads_publish", {"creation_id": container["id"], "access_token": token})
            ids.append(result.get("id"))
            print(f"Published part {i + 1}/{len(parts)}.")
        except RuntimeError as e:
            error = str(e)
            break

    if error and not ids:
        # Nothing went live: leave the item in the queue so the next run retries it.
        sys.exit(error)

    posted.append({
        "parts": parts,
        "status": "posted" if not error else f"partial ({len(ids)}/{len(parts)} published)",
        "threads_ids": ids,
        "date": today,
        "slot": slot,
        "posted_at": datetime.now(tz).isoformat(timespec="minutes"),
    })
    save(POSTED_FILE, posted)
    save(QUEUE_FILE, remaining)
    if error:
        # Some parts are live: never repost them. Record it and alert by failing the run.
        print(f"::error::Thread only partly published ({len(ids)}/{len(parts)}). {error}")
        sys.exit(1)
    print(f"Posted (slot {slot}). {len(remaining)} items left in the queue.")
    if len(remaining) <= 10:
        print("::warning::Queue is almost empty. Ask Claude for the next batch.")


def overdue_count(minutes):
    """How many dated queue items are at least `minutes` past their time."""
    cfg = load(CONFIG_FILE, {}) or {}
    tz = ZoneInfo(cfg.get("timezone", "America/New_York"))
    cutoff = datetime.now(tz) - timedelta(minutes=minutes)
    n = 0
    for it in load(QUEUE_FILE, []):
        if isinstance(it, dict) and it.get("at"):
            if datetime.strptime(it["at"], "%Y-%m-%d %H:%M").replace(tzinfo=tz) <= cutoff:
                n += 1
    return n


if __name__ == "__main__":
    before = len(load(POSTED_FILE, []))
    main()
    # GitHub sometimes starts scheduled runs late or skips one. If we just posted and
    # another item is already 25+ minutes overdue, post one more now so the day catches up.
    if os.environ.get("FORCE_POST") != "1" and len(load(POSTED_FILE, [])) > before and overdue_count(25):
        print("Catching up: posting one more overdue item.")
        main()
