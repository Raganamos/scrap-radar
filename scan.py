#!/usr/bin/env python3
"""Scrap Radar scanner. Pulls free-stuff listings, scores them for scrap/resale
value, geocodes them and writes listings.json for the radar page.
  python scan.py            live scan (runs in GitHub Actions)
  python scan.py --seed F   build from a seed file of 'path|title|hood' lines
"""
import json, re, sys, time, hashlib, os, html, urllib.request
from datetime import datetime, timezone

CFG = json.load(open("config.json"))
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

SKIP = r"mattress|sofa|couch|love ?seat|recliner|sectional|\bcats?\b|kitten|\bdog\b|puppy|rooster|chicken|hens\b|animals|mulch|manure|\bdirt\b|topsoil|eggs?\b|egg carton|dinner|meal|pantry|pick-?up and disposal|removal|wanted|we need|i need|appraisal|valuing|service needed|styrofoam|christmas|halloween|isopod|cactus|aloe|digital|greeting card|incontinence|cpap|diabetic|pillow|crushed shell|bamboo|\bshow\b|koozies|jewels of opar|mocasin"
RULES = [  # (category, score, regex) first match wins
 ("scrap", 5, r"copper|scrap|aluminum|stainless|\bmetals?\b|punch press|cnc|truck box"),
 ("electronics", 5, r"network|switch|access point|camera|server|laptop|computer"),
 ("vehicle", 4, r"boat|trailer|camper|power chair|\bmotor\b|engine|tire|sprocket|brake|truck bed|hover ?board"),
 ("appliance", 4, r"washer|washing machine|dryer|stove|fridge|refrigerator|dishwasher|microwave|appliance|grill|smoker|garage opener|copier"),
 ("electronics", 4, r"monitor|receiver|printer|solar|\btvs?\b|vizio|visio|sony|typewriter|converter|vacuum|inverter|handset"),
 ("resale", 4, r"vinyl|records|tool|paddle board|bike|bicycle|mower|impact window|basketball|treadmill|exercise|gym|shelving|cages|filing cabinet|diesel|hot tub|shed|hospital bed|drexel|ethan allen|home brew"),
 ("materials", 3, r"plywood|lumber|planks|pallets?|\bwood\b|tile|door|sinks?|faucet|countertop|fence|trim|beadboard|t1-11|drywall|window|plumbing|hinges|clamps|hoses|supply lines|fluorescent|roofing|marble|shop light|buckets?"),
 ("furniture", 2, r"dresser|table|chairs?|cabinet|hutch|desk|bookshel|bookcase|bench|headboard|bed ?frame|bedroom|bunk|stools|rack|entertainment|tv stand|wall unit|ottoman|crib|piano|organ"),
 ("curb", 3, r"curb|free stuff|misc|left over|flea market"),
]
CITY = {"lakeland":(28.04,-81.95),"auburndale":(28.065,-81.789),"bartow":(27.896,-81.843),"mulberry":(27.895,-81.973),"nichols":(27.89,-82.03),"plant-city":(28.018,-82.113),"dover":(27.994,-82.22),"seffner":(27.984,-82.276),"brandon":(27.938,-82.286),"valrico":(27.938,-82.236),"riverview":(27.866,-82.326),"tampa":(27.95,-82.46),"lutz":(28.151,-82.461),"odessa":(28.194,-82.59),"land-lakes":(28.219,-82.457),"wesley-chapel":(28.24,-82.33),"zephyrhills":(28.233,-82.181),"dade-city":(28.365,-82.196),"ruskin":(27.72,-82.433),"sun-city-center":(27.718,-82.352),"wimauma":(27.712,-82.299),"saint-petersburg":(27.77,-82.66),"pinellas-park":(27.843,-82.699),"bay-pines":(27.814,-82.778),"seminole":(27.84,-82.791),"largo":(27.909,-82.787),"clearwater-beach":(27.978,-82.827),"clearwater":(27.966,-82.80),"belleair-beach":(27.92,-82.84),"dunedin":(28.02,-82.772),"palm-harbor":(28.078,-82.764),"oldsmar":(28.034,-82.665),"safety-harbor":(27.99,-82.693),"tarpon-springs":(28.146,-82.757),"holiday":(28.188,-82.74),"elfers":(28.217,-82.722),"new-port-richey":(28.244,-82.719),"port-richey":(28.272,-82.72),"hudson":(28.364,-82.693),"aripeka":(28.43,-82.66),"spring-hill":(28.477,-82.525),"brooksville":(28.555,-82.388),"palmetto":(27.521,-82.572),"ellenton":(27.522,-82.528),"bradenton-beach":(27.467,-82.70),"bradenton":(27.499,-82.575),"oneco":(27.45,-82.55),"parrish":(27.588,-82.425),"sarasota":(27.336,-82.531),"bradley":(27.80,-81.98)}
HOOD = {"gulfport":(27.748,-82.703),"st pete beach":(27.725,-82.741),"madeira beach":(27.798,-82.797),"south pasadena":(27.755,-82.738),"coquina key":(27.737,-82.632),"maximo":(27.713,-82.683),"azalea":(27.79,-82.74),"euclid":(27.787,-82.645),"22 ave n":(27.792,-82.675),"south westshore":(27.905,-82.525),"south tampa":(27.915,-82.505),"gandy":(27.893,-82.50),"ybor":(27.96,-82.437),"seminole heights":(27.995,-82.46),"forest hills":(28.045,-82.475),"carrollwood":(28.05,-82.50),"westchase":(28.055,-82.61),"town n country":(28.01,-82.577),"tampa palms":(28.09,-82.38),"new tampa":(28.13,-82.35),"bruce b downs":(28.07,-82.39),"highland city":(27.965,-81.878),"south lakeland":(27.98,-81.96),"33810":(28.11,-82.03),"morton":(28.03,-81.955),"lakewood ranch":(27.41,-82.43),"lwr":(27.41,-82.43),"belleair":(27.935,-82.806),"east lake":(28.11,-82.69),"starkey":(28.2,-82.62)}

def classify(title):
    t = title.lower()
    if re.search(SKIP, t) and not re.search(r"scrap|cages|metal", t): return ("skip", 0)
    for cat, sc, rx in RULES:
        if re.search(rx, t): return (cat, sc)
    return ("other", 1)

def area_geo(path, hood, lid):
    h = (hood or "").lower(); slug = path.strip("/").split("/")[-2] if "/" in path.strip("/") else path
    pt = next((v for k, v in HOOD.items() if k in h), None)
    if not pt:
        pt = next((v for k, v in sorted(CITY.items(), key=lambda kv: -len(kv[0])) if slug.startswith(k + "-") or slug == k), None)
    if not pt: return None
    d = hashlib.md5(lid.encode()).digest()   # small stable offset so pins in one area don't stack
    return (round(pt[0] + (d[0] - 128) / 128 * 0.006, 5), round(pt[1] + (d[1] - 128) / 128 * 0.006, 5))

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")

def live_rows():
    rows, seen = [], set()
    for s in CFG["scans"]:
        page = get(f"https://{s['site']}.craigslist.org/search/zip?lat={s['lat']}&lon={s['lon']}&search_distance={s['miles']}")
        for m in re.finditer(r'<li class="cl-static-search-result"[^>]*>\s*<a href="([^"]+)">(.*?)</a>', page, re.S):
            url, body = m.group(1), m.group(2)
            t = re.search(r'class="title">(.*?)</div>', body, re.S); l = re.search(r'class="location">(.*?)</div>', body, re.S)
            lid = re.sub(r"\.html$", "", url.rstrip("/").split("/")[-1])
            if lid in seen or not t: continue
            seen.add(lid)
            rows.append((url, html.unescape(t.group(1)).strip(), html.unescape(l.group(1)).strip() if l else "", lid))
        time.sleep(2)
    return rows

def main():
    seed = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--seed" else None
    old = {x["id"]: x for x in json.load(open("listings.json"))["items"]} if os.path.exists("listings.json") else {}
    exact = json.load(open("exact.json")) if os.path.exists("exact.json") else {}
    status = {"ok": True, "at": NOW, "source": "seed" if seed else "live"}
    try:
        if seed:
            rows = []
            for ln in open(seed):
                if "|" not in ln: continue
                p, t, h = [x.strip() for x in ln.rstrip("\n").split("|", 2)]
                rows.append(("https://www.craigslist.org/view/d/" + p, t, h, p.split("/")[-1]))
        else:
            rows = live_rows()
            if len(rows) < 20: raise RuntimeError(f"only {len(rows)} listings parsed")
    except Exception as e:
        status.update(ok=False, error=str(e)[:200]); json.dump(status, open("status.json", "w")); print("SCAN FAILED", e); return
    items, lookups = [], 0
    for url, title, hood, lid in rows:
        cat, score = classify(title)
        if cat == "skip": continue
        it = {"id": lid, "t": title[:110], "h": hood[:60], "u": url, "c": cat, "s": score, "first": old.get(lid, {}).get("first", NOW)}
        ex = exact.get(lid)
        if not ex and not seed and score >= 3 and lookups < CFG.get("max_detail_lookups", 25):
            lookups += 1
            try:   # one polite look at the posting for its map pin and post date
                pg = get(url); time.sleep(2)
                la = re.search(r'data-latitude="([-\d.]+)"', pg); lo = re.search(r'data-longitude="([-\d.]+)"', pg)
                dt = re.search(r'datetime="([^"]+)"', pg)
                if la and lo: ex = exact[lid] = {"la": float(la.group(1)), "lo": float(lo.group(1)), "posted": dt.group(1)[:16] if dt else ""}
            except Exception: pass
        if ex:
            it.update(la=ex["la"], lo=ex["lo"], px="exact")
            for k in ("posted", "n", "s"):
                if ex.get(k): it[k] = ex[k]
        else:
            g = area_geo(url.replace("https://", ""), hood, lid)
            if not g: continue
            it.update(la=g[0], lo=g[1], px="area")
        items.append(it)
    live_ids = {r[3] for r in rows}
    json.dump({k: v for k, v in exact.items() if k in live_ids or seed}, open("exact.json", "w"), indent=0)
    json.dump({"scanned": NOW, "count": len(items), "items": items}, open("listings.json", "w"), separators=(",", ":"))
    status["count"] = len(items); json.dump(status, open("status.json", "w"))
    print("wrote", len(items), "items;", lookups, "detail lookups")

main()
