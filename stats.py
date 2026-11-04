"""Read-only: print views/likes/replies for recent posts, plus publishing quota."""
import json, os, urllib.request, urllib.parse
API = "https://graph.threads.net/v1.0"; T = os.environ["THREADS_TOKEN"]
def get(path, **p):
    p["access_token"] = T
    try:
        with urllib.request.urlopen(f"{API}/{path}?" + urllib.parse.urlencode(p), timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode()[:300]}
print("QUOTA", get("me/threads_publishing_limit", fields="quota_usage,config,reply_quota_usage"))
print("ACCOUNT", get("me/threads_insights", metric="views,followers_count", since=1761696000))
posted = json.load(open("posted.json"))
for x in posted[-130:]:
    ids = x.get("threads_ids") or []
    if not ids: continue
    r = get(f"{ids[0]}/insights", metric="views,likes,replies,reposts,shares")
    m = {d["name"]: d["values"][0]["value"] for d in r.get("data", [])} if "data" in r else r
    print(x.get("slot"), len(x["parts"]), m, x["parts"][0][:45].replace("\n", " "))
