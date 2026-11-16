#!/usr/bin/env python3
"""Build pterodactyl.castafero.com: strange, unexplained photos and videos people have taken.

Pulls photo and video posts from Reddit's paranormal, UFO and cryptid communities (public RSS)
and headlines from Google News, sorts them into categories, and merges them into items.json, an
archive that grows run by run (so a source that blocks us for a day costs nothing).
Standard library only. Usage: python3 build.py [out_dir]
"""
import html, json, os, re, sys, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

UA = "castafero-strange/1.0 (+https://pterodactyl.castafero.com)"
NOW = datetime.now(timezone.utc)
ARCHIVE = "items.json"          # committed by the workflow; the site's memory
KEEP = 800                      # archive size cap, newest/top kept

SUBS = "HighStrangeness+UFOs+UFOB+UAP+Cryptozoology+bigfoot+Paranormal+Ghosts+Humanoidencounters+UnexplainedPhotos"
REDDIT = [
    f"https://www.reddit.com/r/{SUBS}/top/.rss?t=week&limit=100",
    f"https://www.reddit.com/r/{SUBS}/hot/.rss?limit=100",
    "https://www.reddit.com/search.rss?" + urllib.parse.urlencode(
        {"q": "pterodactyl OR pterosaur OR thunderbird OR ropen sighting", "sort": "top", "t": "year", "limit": 50}),
]
GNEWS = ["pterodactyl sighting", "pterosaur sighting", "UFO video", "UAP footage", "cryptid sighting",
         "unexplained lights sky", "ghost caught on camera", "bigfoot video"]

CATS = [  # first match wins; order matters (pterodactyl before generic creatures)
    ("pterodactyl", r"pterodactyl\w*|pterosaur\w*|pteranodon|thunderbird|ropen|flying (reptile|dinosaur)|kongamato|giant (bird|wings?)"),
    ("ufo", r"\bufos?\b|\buaps?\b|\bufob\b|orbs?\b|tic.?tac|saucer|drones?|aliens?|disclosure|aaro|craft\b|triangle"),
    ("cryptid", r"cryptid\w*|bigfoot|sasquatch|yeti|skinwalker|dogman|chupacabra|mothman|wendigo|creature|humanoid|lake monster|nessie"),
    ("ghost", r"ghosts?\b|paranormal|haunt\w*|spirits?\b|apparition|shadow (figure|person|people)|poltergeist|evp"),
    ("sky", r"\blights?\b|\bsky\b|ball lightning|meteor|fireball|cloud|aurora|sound|hum\b"),
]
CAT_RE = [(c, re.compile(p, re.I)) for c, p in CATS]
SUB_CAT = {"ufos": "ufo", "ufob": "ufo", "uap": "ufo", "cryptozoology": "cryptid", "bigfoot": "cryptid",
           "humanoidencounters": "cryptid", "paranormal": "ghost", "ghosts": "ghost"}
BLOCK = re.compile(r"\b(nsfw|nsfl|gore|corpse|dead body|porn|onlyfans|giveaway|for sale|buy now|promo code)\b", re.I)


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def iso(d):
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def category(text, sub=""):
    for c, rx in CAT_RE[:1]:   # a pterodactyl mention anywhere beats the subreddit's default
        if rx.search(text):
            return c
    if sub.lower() in SUB_CAT:
        return SUB_CAT[sub.lower()]
    for c, rx in CAT_RE:
        if rx.search(text):
            return c
    return "strange"


def youtube_id(url):
    m = re.search(r"(?:youtube\.com/(?:watch\?v=|shorts/|embed/)|youtu\.be/)([\w-]{11})", url or "")
    return m.group(1) if m else None


def media_kind(url):
    u = (url or "").lower()
    if youtube_id(u) or "v.redd.it" in u or re.search(r"\.(mp4|webm|mov|m3u8)\b", u) or "streamable.com" in u:
        return "video"
    return "image"


def reddit():
    A, M = "{http://www.w3.org/2005/Atom}", "{http://search.yahoo.com/mrss/}"
    out = []
    for i, url in enumerate(REDDIT):
        if i:
            time.sleep(30)   # Reddit rate-limits unauthenticated RSS hard
        try:
            root = ET.fromstring(get(url))
        except Exception as err:
            print("reddit failed:", url, err, file=sys.stderr)
            continue
        for e in root.iter(A + "entry"):
            thumb = e.find(M + "thumbnail")
            content = e.findtext(A + "content") or ""
            if thumb is None:
                continue   # text-only post
            link = re.search(r'href="([^"]+)">\[link\]', content)
            media = html.unescape(link.group(1)) if link else ""
            post = (e.find(A + "link").get("href") if e.find(A + "link") is not None else "")
            media = urllib.parse.urljoin("https://www.reddit.com/", media) if media else ""   # crossposts are relative
            if "reddit.com" in media and "/gallery/" not in media and media.rstrip("/") == post.rstrip("/"):
                media = ""
            title = clean(e.findtext(A + "title"))
            sub = (e.find(A + "category").get("term") if e.find(A + "category") is not None else "")
            body = clean(content.split("submitted by")[0])
            try:
                d = datetime.fromisoformat(e.findtext(A + "published") or e.findtext(A + "updated"))
            except Exception:
                d = NOW
            out.append({
                "id": "r:" + (e.findtext(A + "id") or post), "title": title, "text": body[:300],
                "url": post, "media": media, "thumb": html.unescape(thumb.get("url")),
                "kind": media_kind(media), "yt": youtube_id(media),
                "src": f"r/{sub}" if sub else "Reddit", "date": iso(d), "cat": category(f"{title} {body}", sub),
                "score": 0,
            })
    return out


def gnews():
    out, seen = [], set()
    for q in GNEWS:
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
            {"q": f"{q} when:30d", "hl": "en-US", "gl": "US", "ceid": "US:en"})
        try:
            root = ET.fromstring(get(url))
        except Exception as err:
            print("google news failed:", q, err, file=sys.stderr)
            continue
        for it in root.iter("item"):
            title = clean(it.findtext("title"))
            pub = next((c.text.strip() for c in it if c.tag.endswith("source") and (c.text or "").strip()), "")
            title = re.sub(r"\s+-\s+[^-]{2,60}$", "", title)
            key = re.sub(r"\W+", " ", title.lower()).strip()
            if not title or key in seen:
                continue
            seen.add(key)
            try:
                d = iso(parsedate_to_datetime(it.findtext("pubDate")))
            except Exception:
                d = iso(NOW)
            out.append({"title": title, "src": pub, "url": it.findtext("link") or "", "date": d, "cat": category(title)})
        time.sleep(1)
    out.sort(key=lambda x: x["date"], reverse=True)
    return out[:60]


def merge(old, new):
    by_id = {i["id"]: i for i in old}
    for i in new:
        prev = by_id.get(i["id"])
        if prev:
            i["first"] = prev.get("first", prev["date"])
            i["score"] = max(i["score"], prev.get("score", 0))
        else:
            i["first"] = iso(NOW)
        by_id[i["id"]] = i
    items = [i for i in by_id.values() if not BLOCK.search(f"{i['title']} {i['text']}")]
    items.sort(key=lambda i: i["date"], reverse=True)
    return items[:KEEP]


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    try:
        with open(ARCHIVE, encoding="utf-8") as fh:
            old = json.load(fh)
    except FileNotFoundError:
        old = []
    fresh = reddit()
    items = merge(old, fresh)
    if not items:
        sys.exit("no items from any source and no archive; keeping the previous site")
    with open(ARCHIVE, "w", encoding="utf-8") as fh:
        json.dump(items, fh, separators=(",", ":"))
    data = {"updated": iso(NOW), "items": items, "news": gnews()}
    with open(os.path.join(out_dir, "data.json"), "w", encoding="utf-8") as fh:
        json.dump(data, fh, separators=(",", ":"))
    by = {}
    for i in items:
        by[i["cat"]] = by.get(i["cat"], 0) + 1
    print(f"{len(fresh)} fetched, {len(items)} in archive {by}, {len(data['news'])} headlines")


if __name__ == "__main__":
    assert category("Pterodactyl spotted over Texas", "UFOs") == "pterodactyl"
    assert category("weird thing", "Ghosts") == "ghost" and category("orb over the lake") == "ufo"
    assert youtube_id("https://youtu.be/ApYGHYyItdw?t=3") == "ApYGHYyItdw" and media_kind("https://v.redd.it/x") == "video"
    main(sys.argv[1] if len(sys.argv) > 1 else "_site")
