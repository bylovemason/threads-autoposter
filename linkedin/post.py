"""
LinkedIn auto-poster for Love Mason.

Runs every hour on GitHub Actions (see .github/workflows/linkedin-post.yml).
Each item in linkedin/queue.json has an "at" time ("YYYY-MM-DD HH:MM", in the
timezone set in linkedin/config.json). Once that time has passed, the item is
published to Love Mason's personal LinkedIn profile through LinkedIn's
official Posts API and moved to linkedin/posted.json.

Queue item:
  {
    "at": "2026-11-03 08:30",
    "text": "The post text. Line breaks are kept.",
    "image": "cards/2026-11-03.png",      # optional, path inside linkedin/
    "alt": "Short image description"        # optional
  }

No extra packages needed: standard Python only.
"""

import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

API = os.environ.get("LINKEDIN_API_BASE", "https://api.linkedin.com")
HERE = os.path.dirname(os.path.abspath(__file__))
QUEUE_FILE = os.path.join(HERE, "queue.json")
POSTED_FILE = os.path.join(HERE, "posted.json")
CONFIG_FILE = os.path.join(HERE, "config.json")
MAX_CHARS = 3000


def load(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


# LinkedIn reads post text as "little text": characters like ( ) [ ] @ # *
# are markup, and an unescaped one can silently cut the post off. Escape them
# all, then turn real #hashtags back into LinkedIn's hashtag format.
RESERVED = set("\\|{}@[]()<>#*_~")
HASHTAG = re.compile(r"(?<![\w\\])\\#([A-Za-z][A-Za-z0-9_]*)")


def to_little_text(text):
    escaped = "".join("\\" + c if c in RESERVED else c for c in text)
    return HASHTAG.sub(lambda m: "{hashtag|\\#|" + m.group(1).replace("\\_", "_") + "}", escaped)


class LinkedIn:
    def __init__(self, token, version):
        self.token = token
        self.version = version

    def request(self, method, path, body=None, raw=None, headers=None, rest=True):
        url = path if path.startswith("http") else f"{API}{path}"
        h = {"Authorization": f"Bearer {self.token}"}
        if rest:
            h["LinkedIn-Version"] = self.version
            h["X-Restli-Protocol-Version"] = "2.0.0"
        data = raw
        if body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        h.update(headers or {})
        req = urllib.request.Request(url, data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                text = r.read().decode(errors="replace")
                return r.status, dict(r.headers), (json.loads(text) if text.strip() else {})
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")
            if e.code == 426 and rest:
                raise VersionTooOld(msg) from None
            raise RuntimeError(f"LinkedIn API error {e.code}: {msg}") from None

    def call(self, method, path, **kw):
        """Call a /rest endpoint. If LinkedIn says our version is retired or
        not out yet, step to a neighbouring month and try again (up to 6x)."""
        for _ in range(6):
            try:
                return self.request(method, path, **kw)
            except VersionTooOld:
                y, m = int(self.version[:4]), int(self.version[4:6])
                y, m = (y, m - 1) if m > 1 else (y - 1, 12)
                print(f"::warning::LinkedIn-Version not accepted, trying {y}{m:02d}. "
                      f"Update linkedin_version in linkedin/config.json.")
                self.version = f"{y}{m:02d}"
        raise RuntimeError("No accepted LinkedIn-Version found. Set a recent YYYYMM in linkedin/config.json.")

    def person_urn(self):
        urn = os.environ.get("LINKEDIN_PERSON_URN", "").strip()
        if urn:
            return urn if urn.startswith("urn:") else f"urn:li:person:{urn}"
        _, _, me = self.request("GET", "/v2/userinfo", rest=False)
        if not me.get("sub"):
            raise RuntimeError("Could not read your LinkedIn member ID. Make sure the token has the openid and profile scopes.")
        return f"urn:li:person:{me['sub']}"

    def upload_image(self, owner, path):
        _, _, init = self.call("POST", "/rest/images?action=initializeUpload",
                               body={"initializeUploadRequest": {"owner": owner}})
        value = init["value"]
        with open(path, "rb") as f:
            data = f.read()
        self.request("PUT", value["uploadUrl"], raw=data, rest=False,
                     headers={"Content-Type": "application/octet-stream"})
        return value["image"]

    def create_post(self, author, text, image_urn=None, alt=""):
        body = {
            "author": author,
            "commentary": to_little_text(text),
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        if image_urn:
            body["content"] = {"media": {"id": image_urn, "altText": alt[:4000]}}
        _, headers, _ = self.call("POST", "/rest/posts", body=body)
        lower = {k.lower(): v for k, v in headers.items()}
        return lower.get("x-restli-id") or lower.get("x-linkedin-id") or ""


class VersionTooOld(Exception):
    pass


def main():
    cfg = load(CONFIG_FILE, None)
    if cfg is None:
        sys.exit("linkedin/config.json is missing.")
    if cfg.get("paused"):
        print("LinkedIn posting is paused in linkedin/config.json. Nothing to do.")
        return

    tz = ZoneInfo(cfg["timezone"])
    now = datetime.now(tz)
    force = os.environ.get("FORCE_POST") == "1"
    queue = load(QUEUE_FILE, [])
    posted = load(POSTED_FILE, [])
    if not queue:
        print("LinkedIn queue is empty. Ask Claude for the next batch.")
        return

    def at_time(it):
        return datetime.strptime(it["at"], "%Y-%m-%d %H:%M").replace(tzinfo=tz) if it.get("at") else None

    if force:
        idx = 0
    else:
        due = [(at_time(it), i) for i, it in enumerate(queue) if at_time(it) and at_time(it) <= now]
        if not due:
            nxt = min((at_time(it) for it in queue if at_time(it)), default=None)
            print(f"{now:%Y-%m-%d %H:%M} {cfg['timezone']}: nothing due."
                  + (f" Next LinkedIn post at {nxt:%Y-%m-%d %H:%M}." if nxt else ""))
            return
        # One post per run, earliest first, so a missed hour never causes a burst.
        _, idx = min(due)

    item = queue[idx]
    remaining = queue[:idx] + queue[idx + 1:]
    text = item.get("text", "").strip()
    image = item.get("image")
    image_path = os.path.join(HERE, image) if image else None

    problem = None
    if not text:
        problem = "empty text"
    elif len(text) > MAX_CHARS:
        problem = f"text is {len(text)} characters, over {MAX_CHARS}"
    elif image_path and not os.path.exists(image_path):
        problem = f"image {image} not found"
    if problem:
        print(f"::warning::Skipping this post: {problem}. Moved to posted.json as 'skipped'.")
        posted.append({**item, "status": f"skipped: {problem}", "checked_at": now.isoformat(timespec="minutes")})
        save(POSTED_FILE, posted)
        save(QUEUE_FILE, remaining)
        return

    token = os.environ.get("LINKEDIN_TOKEN", "").strip()
    if not token:
        sys.exit("LINKEDIN_TOKEN secret is missing. See linkedin/README.md, step 4.")

    if not force:
        delay = random.randint(0, int(cfg.get("max_random_delay_minutes", 5)) * 60)
        print(f"Waiting {delay // 60}m {delay % 60}s before posting.")
        time.sleep(delay)

    li = LinkedIn(token, str(cfg.get("linkedin_version", "202608")))
    try:
        author = li.person_urn()
        image_urn = li.upload_image(author, image_path) if image_path else None
        post_id = li.create_post(author, text, image_urn, item.get("alt", ""))
    except RuntimeError as e:
        msg = str(e)
        if " 401" in msg:
            msg += "\nYour LinkedIn token has probably expired. Make a new one: linkedin/README.md, step 3."
        # Nothing went live, so the post stays in the queue and the next run retries it.
        sys.exit(msg)

    posted.append({**item, "status": "posted", "linkedin_id": post_id,
                   "posted_at": datetime.now(tz).isoformat(timespec="minutes")})
    save(POSTED_FILE, posted)
    save(QUEUE_FILE, remaining)
    print(f"Posted to LinkedIn ({post_id}). {len(remaining)} posts left in the queue.")
    if len(remaining) <= 3:
        print("::warning::LinkedIn queue is almost empty. Ask Claude for the next batch.")


if __name__ == "__main__":
    main()
