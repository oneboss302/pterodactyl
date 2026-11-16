#!/usr/bin/env python3
"""Build pterodactyl.castafero.com data.

Every pterosaur fossil occurrence in the Paleobiology Database (present-day and reconstructed
ancient coordinates, age, genus, family, reference), plus recent pterosaur science news.
Satire outlets are excluded. Standard library only. Usage: python3 build.py [out_dir]
"""
import html, json, os, re, sys, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

UA = "castafero-pterosaurs/1.0 (+https://pterodactyl.castafero.com)"
NOW = datetime.now(timezone.utc)
PBDB = ("https://paleobiodb.org/data1.2/occs/list.json?base_name=Pterosauria"
        "&show=coords,loc,time,class,paleoloc,ref,crmod&vocab=pbdb&limit=all")
PTERO_RE = re.compile(r"\b(pterosaurs?|pterodactyl\w*|pteranodon\w*|quetzalcoatl\w*|azhdarch\w*|rhamphorhynch\w*|"
                      r"hatzegopteryx|anhanguera|tupandactylus|flying reptiles?)\b", re.I)
SATIRE = ["the onion", "theonion", "babylon bee", "babylonbee", "clickhole", "beaverton", "waterford whispers", "daily mash",
          "newsthump", "duffel blog", "reductress", "the hard times", "national report", "world news daily report",
          "worldnewsdailyreport", "empire news", "the shovel", "betoota", "der postillon", "borowitz", "huzlers", "react365",
          "newsbiscuit", "the spoof", "thespoof", "satire", "parody",
          # cryptid / "living pterosaur" sighting sites are not science sources
          "livepterosaur", "living pterosaur", "ropen", "cryptid", "weekly world news"]
NEWS = [
    ("Google News", "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": "pterosaur OR pterodactyl OR pteranodon when:60d", "hl": "en-US", "gl": "US", "ceid": "US:en"}), True),
    ("Bing News", "https://www.bing.com/news/search?" + urllib.parse.urlencode({"q": "pterosaur OR pterodactyl", "format": "rss"}), True),
    ("ScienceDaily", "https://www.sciencedaily.com/rss/fossils_ruins/dinosaurs.xml", False),
    ("Phys.org", "https://phys.org/rss-feed/biology-news/evolution/", False),
]
SCIENCE_RE = re.compile(r"\b(fossil\w*|species|paleontolog\w*|palaeontolog\w*|museum|discover\w*|bones?|skeleton\w*|skull|"
                        r"wingspan|extinct\w*|jurassic|cretaceous|triassic|research\w*|study|studies|scientists?|million years|"
                        r"prehistoric|evolution\w*|specimens?|genus|excavat\w*|ancestor|stomach|diet)\b", re.I)
# viral "sighting" stories are hoaxes, not science
SIGHTING_RE = re.compile(r"\b(filmed|spotted|sighting\w*|viral|caught on (camera|video)|video|footage|claims? (they|to) (have )?seen|"
                         r"cryptid|ropen|thunderbird|chupacabra|alive today|still alive)\b", re.I)

PERIODS = [("Triassic", 251.9, 201.4), ("Jurassic", 201.4, 145.0), ("Cretaceous", 145.0, 66.0)]


def get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def period(mid):
    for name, hi, lo in PERIODS:
        if lo <= mid <= hi:
            return name
    return "Cretaceous" if mid < 145 else "Triassic"


def num(v):
    try:
        return round(float(v), 3)
    except (TypeError, ValueError):
        return None


def fossils():
    recs = json.loads(get(PBDB))["records"]
    out = []
    for r in recs:
        lat, lng = num(r.get("lat")), num(r.get("lng"))
        if lat is None or lng is None:
            continue
        hi, lo = r.get("max_ma"), r.get("min_ma")
        mid = (hi + lo) / 2 if hi is not None and lo is not None else None
        interval = r.get("early_interval", "")
        if r.get("late_interval") and r["late_interval"] != interval:
            interval += f" to {r['late_interval']}"
        out.append({
            "id": int(r["occurrence_no"]), "name": r.get("accepted_name") or r.get("identified_name"),
            "genus": r.get("genus") or "", "family": r.get("family") or "", "rank": r.get("accepted_rank", ""),
            "lat": lat, "lng": lng, "plat": num(r.get("paleolat")), "plng": num(r.get("paleolng")),
            "cc": r.get("cc", ""), "state": r.get("state", ""), "where": r.get("geogcomments", "")[:160],
            "max": hi, "min": lo, "period": period(mid) if mid is not None else "",
            "interval": interval, "ref": (r.get("primary_reference") or "")[:300],
            "added": (r.get("created") or "")[:10], "coll": r.get("collection_no"),
        })
    return out


def news():
    seen, out = set(), []
    for src, url, gn in NEWS:
        try:
            root = ET.fromstring(get(url, timeout=30))
        except Exception as err:
            print("news failed:", src, err, file=sys.stderr)
            continue
        for it in root.iter("item"):
            title = html.unescape(re.sub(r"<[^>]+>", "", it.findtext("title") or "")).strip()
            pub = src
            if gn:
                for c in it:
                    if c.tag.rsplit("}", 1)[-1].lower() == "source" and (c.text or "").strip():
                        pub = c.text.strip()
            if gn:
                title = re.sub(r"\s+-\s+[^-]{2,60}$", "", title)
            desc = html.unescape(re.sub(r"<[^>]+>", " ", it.findtext("description") or ""))
            link = it.findtext("link") or ""
            if "bing.com/news/apiclick" in link:   # unwrap Bing's redirect to the real article
                link = urllib.parse.parse_qs(urllib.parse.urlparse(link).query).get("url", [link])[0]
            key = re.sub(r"\W+", " ", title.lower()).strip()
            text = title + " " + (desc if not gn else "")
            if not title or key in seen or not PTERO_RE.search(text) or not SCIENCE_RE.search(text) or SIGHTING_RE.search(title):
                continue
            blob = f"{pub} {link} {title}".lower()
            if any(s in blob for s in SATIRE):
                continue
            try:
                d = parsedate_to_datetime(it.findtext("pubDate"))
            except Exception:
                d = None
            if d and NOW - d > timedelta(days=180):
                continue
            seen.add(key)
            out.append({"title": title, "src": pub, "url": link,
                        "date": d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if d else None})
    out.sort(key=lambda x: x["date"] or "", reverse=True)
    return out[:30]


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    finds = fossils()
    if len(finds) < 500:
        sys.exit(f"only {len(finds)} fossil records; keeping the previous site")
    data = {"updated": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"), "finds": finds, "news": news(),
            "source": "https://paleobiodb.org/"}
    with open(os.path.join(out_dir, "data.json"), "w", encoding="utf-8") as fh:
        json.dump(data, fh, separators=(",", ":"))
    genera = {f["genus"] for f in finds if f["genus"]}
    print(f"{len(finds)} finds, {len(genera)} genera, {len({f['cc'] for f in finds})} countries, {len(data['news'])} news")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "_site")
