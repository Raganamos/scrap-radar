#!/usr/bin/env python3
"""Scrap Radar scanner. Pulls free-stuff listings, scores them for scrap/resale
value, geocodes them and writes listings.json for the radar page.
  python scan.py            live scan (runs in GitHub Actions)
  python scan.py --seed F   build from a seed file of 'path|title|hood' lines
"""
import json, re, sys, time, hashlib, os, html, urllib.request, urllib.parse
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

ALIAS = {"st pete beach": "st pete beach", "st. pete beach": "st pete beach", "st pete": "saint-petersburg", "st. pete": "saint-petersburg",
         "st petersburg": "saint-petersburg", "st. petersburg": "saint-petersburg", "land o": "land-lakes", "town 'n' country": "town n country",
         "town n country": "town n country", "temple terrace": (28.035, -82.389), "apollo beach": (27.773, -82.407), "gibsonton": (27.853, -82.382),
         "lithia": (27.866, -82.21), "thonotosassa": (28.061, -82.302), "winter haven": (28.022, -81.733), "haines city": (28.114, -81.618),
         "davenport": (28.161, -81.602), "polk city": (28.182, -81.824), "kathleen": (28.121, -82.023), "highland city": "highland city",
         "ulmerton": (27.894, -82.75), "kenneth city": (27.816, -82.72), "indian rocks": (27.875, -82.85), "treasure island": (27.769, -82.769),
         "redington": (27.82, -82.82), "south pasadena": "south pasadena", "tierra verde": (27.692, -82.723), "citrus park": (28.078, -82.57),
         "egypt lake": (28.017, -82.506), "pebble creek": (28.148, -82.345), "fishhawk": (27.851, -82.21), "bloomingdale": (27.893, -82.24),
         "orlando": (28.538, -81.379), "kissimmee": (28.292, -81.408), "clermont": (28.549, -81.773), "sanford": (28.8, -81.273), "leesburg": (28.811, -81.878),
         "lady lake": (28.917, -81.923), "venice": (27.1, -82.454), "englewood": (26.962, -82.352), "north port": (27.044, -82.236), "ocala": (29.187, -82.14),
         "auburndale": (28.065, -81.789), "lake wales": (27.901, -81.586), "frostproof": (27.746, -81.531), "fort meade": (27.752, -81.802),
         "zephyrhills": (28.233, -82.181), "dade city": (28.365, -82.196), "wesley chapel": (28.24, -82.33), "lutz": (28.151, -82.461),
         "odessa": (28.194, -82.59), "trinity": (28.18, -82.68), "palm harbor": (28.078, -82.764), "riverview": (27.866, -82.326),
         "sun city": (27.718, -82.352), "ellenton": (27.522, -82.528), "lakewood ranch": (27.41, -82.43), "myakka": (27.36, -82.16),
         "haines city": (28.114, -81.618), "eagle lake": (27.978, -81.756), "mulberry": (27.895, -81.973), "bartow": (27.896, -81.843)}

def geo_text(text, lid):
    """Place a listing from free text such as 'Pinellas Park, FL' or 'Off Ulmerton, Largo Mall area'."""
    h = (text or "").lower(); pt = None
    for k, v in sorted(ALIAS.items(), key=lambda kv: -len(kv[0])):
        if k in h:
            pt = v if isinstance(v, tuple) else HOOD.get(v) or CITY.get(v); break
    if not pt: pt = next((v for k, v in HOOD.items() if k in h), None)
    if not pt: pt = next((v for k, v in sorted(CITY.items(), key=lambda kv: -len(kv[0])) if k.replace("-", " ") in h), None)
    if not pt: return None
    d = hashlib.md5(lid.encode()).digest()
    return (round(pt[0] + (d[0] - 128) / 128 * 0.006, 5), round(pt[1] + (d[1] - 128) / 128 * 0.006, 5))

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")

PRICE = {}
def cl_parse(page, seen, rows, free_only=False):
    for m in re.finditer(r'<li class="cl-static-search-result"[^>]*>\s*<a href="([^"]+)">(.*?)</a>', page, re.S):
        url, body = m.group(1), m.group(2)
        t = re.search(r'class="title">(.*?)</div>', body, re.S); l = re.search(r'class="location">(.*?)</div>', body, re.S)
        p = re.search(r'class="price">\s*\$?([\d,]+)', body)
        price = int(p.group(1).replace(",", "")) if p else 0
        lid = re.sub(r"\.html$", "", url.rstrip("/").split("/")[-1])
        if lid in seen or not t or (free_only and price > 1): continue
        seen.add(lid); PRICE[lid] = price
        rows.append((url, html.unescape(t.group(1)).strip(), html.unescape(l.group(1)).strip() if l else "", lid, "cl"))

def src_craigslist(seen, rows):
    for s in CFG["scans"]:
        base = f"https://{s['site']}.craigslist.org/search/%s?lat={s['lat']}&lon={s['lon']}&search_distance={s['miles']}"
        cl_parse(get(base % "zip"), seen, rows); time.sleep(2)
        for q in CFG.get("cl_queries", []):   # free things people post in the for-sale sections ("" = every $0 listing)
            try: cl_parse(get(base % "sss" + "&max_price=1" + ("&query=" + urllib.parse.quote(q) if q else "")), seen, rows, free_only=True)
            except Exception: pass
            time.sleep(2)

def src_offerup(seen, rows):
    for z, q in [(z, q) for z in CFG.get("offerup_zips", []) for q in CFG.get("offerup_queries", ["free"])]:
        try: pg = get(f"https://offerup.com/search?q={urllib.parse.quote(q)}&price_max=0&zipcode={z}&radius=30")
        except Exception: continue
        nd = json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', pg, re.S).group(1))
        for t in nd["props"]["pageProps"]["searchFeedResponse"]["looseTiles"]:
            x = t.get("listing") or {}
            try: free = float(x.get("price") or 1) == 0
            except ValueError: free = False
            lid = "ou-" + str(x.get("listingId", ""))
            if not x.get("listingId") or not free or lid in seen: continue
            seen.add(lid)
            IMG[lid] = ((x.get("image") or {}).get("url") or "")
            rows.append(("https://offerup.com/item/detail/" + x["listingId"], (x.get("title") or "").strip(), x.get("locationName") or "", lid, "ou"))
        time.sleep(2)

def src_trashnothing(seen, rows):
    for a in CFG.get("trashnothing", []):
        pg = get(f"https://trashnothing.com/beta/browse?latitude={a['lat']}&longitude={a['lon']}&radius={a['radius_m']}&types=offer")
        for m in re.finditer(r'<a href="(/post/(\d+)/[^"]*)"[^>]*class="[^"]*post-list-item offer[^"]*">.*?<span class="post-title">(.*?)</span>\s*<!', pg, re.S):
            lid = "tn-" + m.group(2)
            if lid in seen: continue
            seen.add(lid)
            full = re.sub(r"\s+", " ", html.unescape(re.sub(r"<span.*?</span>", "", m.group(3), flags=re.S))).strip()
            loc = re.search(r"\(([^()]*)\)\s*$", full)
            rows.append(("https://trashnothing.com" + m.group(1), re.sub(r"\s*\([^()]*\)\s*$", "", full), loc.group(1) if loc else "", lid, "tn"))
        time.sleep(2)

def src_browser(seen, rows):
    p = "browser_rows.json"
    if not os.path.exists(p) or time.time() - os.path.getmtime(p) > 8 * 3600: return
    for r in json.load(open(p, encoding="utf-8")).get("rows", []):
        lid = r["id"]
        if lid in seen: continue
        seen.add(lid); PRICE[lid] = r.get("p", 0)
        if r.get("img"): IMG[lid] = r["img"]
        rows.append((r["u"], r["t"], r.get("h", ""), lid, r["src"]))

IMG = {}
SOURCES = {"craigslist": src_craigslist, "offerup": src_offerup, "trashnothing": src_trashnothing, "signed_in_sites": src_browser}

def live_rows(status):
    rows, seen = [], set(); status["sources"] = {}
    for name, fn in SOURCES.items():
        n = len(rows)
        try: fn(seen, rows); status["sources"][name] = len(rows) - n
        except Exception as e: status["sources"][name] = "failed: " + str(e)[:80]
    return rows

# ---------- value estimates ----------
PRICES = CFG.get("scrap_prices", {})
RULE_W = [(r"washer|washing machine", 150, "steel"), (r"dryer", 120, "steel"), (r"fridge|refrigerator|freezer", 220, "steel"), (r"stove|oven|range", 150, "steel"),
          (r"dishwasher", 80, "steel"), (r"microwave", 30, "steel"), (r"water heater", 110, "steel"), (r"grill|smoker", 60, "steel"), (r"treadmill", 200, "steel"),
          (r"filing cabinet", 50, "steel"), (r"shelving", 80, "steel"), (r"mower", 60, "steel"), (r"bed ?frame|headboard", 40, "steel"), (r"cages?", 40, "steel"),
          (r"copper", 15, "copper"), (r"alumin", 20, "aluminum"), (r"stainless", 40, "stainless"), (r"\btvs?\b|monitor|printer|copier", 30, "ewaste")]
EST_PROMPT = """You estimate what a free second-hand item is worth to someone who hauls things away to resell or scrap, in Florida.
Listing title: "%s"
Give typical real-world numbers for this KIND of item, not zeros:
- resale_low: dollars it sells for locally as-is / untested (integer; 0 only if nobody buys this kind of thing used)
- resale_high: dollars a clean working one sells for locally, used (integer)
- weight_lb: typical total weight of the item in pounds if it went to a scrap yard (integer; 0 only for non-metal things like wood, books, clothes)
- metal: main scrap metal: "steel", "copper", "aluminum", "stainless", "ewaste" (electronics) or "none"
- confidence: "high" if the title names a specific item, "medium" if it names a kind of item, "low" if vague
- why: under 12 words
Examples: washing machine -> {"resale_low":20,"resale_high":120,"weight_lb":150,"metal":"steel","confidence":"medium","why":"common appliance, steady used demand"}
aluminum boat no motor -> {"resale_low":150,"resale_high":600,"weight_lb":250,"metal":"aluminum","confidence":"medium","why":"small boats resell; hull is aluminum"}
"curb alert" -> {"resale_low":0,"resale_high":0,"weight_lb":0,"metal":"none","confidence":"low","why":"no item named"}
Reply with one JSON object only."""

def gpu_busy():
    """True while a game or other heavy GPU work is running: the value AI then waits, so it never competes with priority use."""
    try:
        import subprocess
        out = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        util, used, total = [float(x) for x in out.strip().splitlines()[0].split(",")]
        ollama_on_gpu = 0.0
        try:
            ps = json.loads(urllib.request.urlopen("http://localhost:11434/api/ps", timeout=5).read())
            ollama_on_gpu = sum(m.get("size_vram", 0) for m in ps.get("models", [])) / 1048576
        except Exception: pass
        other = used - ollama_on_gpu
        return util >= CFG.get("gpu_busy_util", 40) and ollama_on_gpu == 0 or other > total - 6500
    except Exception:
        return False

def llm_estimate(title):
    body = {"model": CFG.get("estimate_model", "qwen3.5:9b"), "stream": False, "format": "json", "think": False, "keep_alive": "2m",
            "options": {"temperature": 0, "num_predict": 160}, "messages": [{"role": "user", "content": EST_PROMPT % title.replace('"', "'")}]}
    req = urllib.request.Request("http://localhost:11434/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    out = json.loads(urllib.request.urlopen(req, timeout=45).read())["message"]["content"]
    j = json.loads(out)
    num = lambda k: max(0, min(20000, int(float(j.get(k) or 0))))
    return {"rl": num("resale_low"), "rh": max(num("resale_low"), num("resale_high")), "w": min(num("weight_lb"), 5000),
            "m": j.get("metal") if j.get("metal") in PRICES else "none", "cf": j.get("confidence") if j.get("confidence") in ("low", "medium", "high") else "low",
            "why": str(j.get("why", ""))[:80], "by": "ai"}

RULE_R = [(r"riding mower|lawn tractor", 150, 600), (r"golf cart", 400, 1500), (r"camper|travel trailer", 300, 1500), (r"utility trailer|trailer", 200, 900),
          (r"boat", 150, 800), (r"power chair|mobility scooter|wheelchair", 100, 500), (r"hospital bed", 50, 250), (r"shed", 150, 700),
          (r"hot tub|spa\b", 0, 300), (r"treadmill|elliptical|home gym|exercise bike|weight bench|gym", 40, 250), (r"pressure washer|generator", 40, 200),
          (r"mower", 30, 150), (r"chain ?saw|leaf blower|trimmer|weed eater", 20, 90), (r"tools?\b|drill|saw\b|compressor|welder", 20, 150),
          (r"\bbikes?\b|bicycles?", 25, 120), (r"kayak|paddle ?board|canoe", 60, 250), (r"grill|smoker", 20, 120),
          (r"refrigerator|fridge|freezer", 40, 250), (r"washer|dryer|washing machine", 25, 175), (r"stove|range|oven", 30, 175), (r"dishwasher", 15, 80),
          (r"\btvs?\b|television|sony|vizio|samsung tv", 15, 90), (r"monitor", 10, 40), (r"receiver|amplifier|speaker", 20, 120), (r"printer|copier", 0, 40),
          (r"network|switch|router|access point|camera", 10, 80), (r"laptop|computer|\bpc\b|xbox|playstation|ps[345]|nintendo", 30, 200),
          (r"vinyl|records", 20, 150), (r"piano|organ", 0, 0), (r"dresser|cabinet|hutch|desk|table", 10, 80), (r"pallets?", 0, 10), (r"tires?", 0, 40)]

def rule_estimate(title):
    t = title.lower()
    w, m = 0, "none"
    for rx, ww, mm in RULE_W:
        if re.search(rx, t): w, m = ww, mm; break
    rl = rh = 0
    for rx, a, b in RULE_R:
        if re.search(rx, t): rl, rh = a, b; break
    if not w and not rh: return None
    return {"rl": rl, "rh": rh, "w": w, "m": m, "cf": "low", "why": "typical price and weight for this kind of item", "by": "rule"}

AI_NOTE = {}
def add_values(items, seed):
    cache = json.load(open("est.json")) if os.path.exists("est.json") else {}
    budget, ai_ok, done = CFG.get("max_estimates_per_run", 30), not seed, 0
    if ai_ok and gpu_busy(): ai_ok = False; AI_NOTE["note"] = "paused: GPU busy (game or other heavy work running)"
    for it in sorted(items, key=lambda i: -i["s"]):
        e = cache.get(it["id"])
        if not e and ai_ok and it["s"] >= 3 and done < budget:
            try: e = llm_estimate(it["t"]); done += 1
            except Exception as ex:
                ai_ok = False; AI_NOTE["note"] = "skipped: local model too slow or not running"   # try again next scan
        if not e: e = rule_estimate(it["t"])
        if not e: continue
        if e.get("by") == "ai": cache[it["id"]] = e
        sc = round(e["w"] * PRICES.get(e["m"], 0))
        v = {"rl": e["rl"], "rh": e["rh"], "sc": sc, "cf": e["cf"], "why": e["why"], "by": e["by"]}
        if e["w"] and e["m"] != "none": v["w"], v["m"] = e["w"], e["m"]
        v["best"] = max(sc, e["rl"])   # conservative: scrap value or the as-is resale figure, whichever is higher
        it["v"] = v
    live = {i["id"] for i in items}
    json.dump({k: v for k, v in cache.items() if k in live}, open("est.json", "w"))
    return done

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
                rows.append(("https://www.craigslist.org/view/d/" + p, t, h, p.split("/")[-1], "cl"))
        else:
            rows = live_rows(status)
            if len(rows) < 20: raise RuntimeError(f"only {len(rows)} listings parsed")
    except Exception as e:
        status.update(ok=False, error=str(e)[:200]); json.dump(status, open("status.json", "w")); print("SCAN FAILED", e); return
    items, lookups = [], 0
    for url, title, hood, lid, src in rows:
        cat, score = classify(title)
        if cat == "skip": continue
        it = {"id": lid, "t": title[:110], "h": hood[:60], "u": url, "c": cat, "s": score, "src": src, "first": old.get(lid, {}).get("first", NOW)}
        ex = exact.get(lid)
        if not ex and not seed and src == "cl" and score >= 3 and lookups < CFG.get("max_detail_lookups", 25):
            lookups += 1
            try:   # one polite look at the posting for its map pin and post date
                pg = get(url); time.sleep(2)
                la = re.search(r'data-latitude="([-\d.]+)"', pg); lo = re.search(r'data-longitude="([-\d.]+)"', pg)
                dt = re.search(r'datetime="([^"]+)"', pg)
                im = re.search(r'https://images\.craigslist\.org/[\w_]+_(?:300x300|600x450)\.jpg', pg)
                if la and lo: ex = exact[lid] = {"la": float(la.group(1)), "lo": float(lo.group(1)), "posted": dt.group(1)[:16] if dt else "", "img": im.group(0) if im else ""}
            except Exception: pass
        if ex:
            it.update(la=ex["la"], lo=ex["lo"], px="exact")
            for k in ("posted", "n", "s", "img"):
                if ex.get(k): it[k] = ex[k]
        else:
            g = (area_geo(url.replace("https://", ""), hood, lid) if src == "cl" else None) or geo_text(hood, lid)
            if not g and src == "nd": g = geo_text(CFG.get("home_area", "lakeland"), lid)
            if not g: continue
            it.update(la=g[0], lo=g[1], px="area")
        if IMG.get(lid): it["img"] = IMG[lid]
        if PRICE.get(lid): it["p"] = PRICE[lid]
        items.append(it)
    live_ids = {r[3] for r in rows}
    json.dump({k: v for k, v in exact.items() if k in live_ids or seed}, open("exact.json", "w"), indent=0)
    status["estimated_this_run"] = add_values(items, seed)
    if AI_NOTE: status["ai_note"] = AI_NOTE["note"]
    status["ai_backlog"] = sum(1 for i in items if i["s"] >= 3 and (i.get("v") or {}).get("by") != "ai")
    try: status["signed_in"] = json.load(open("browser_rows.json", encoding="utf-8")).get("status", {})
    except Exception: pass
    status["by_source"] = {k: sum(1 for i in items if i.get("src") == k) for k in ("cl", "ou", "tn", "fb", "nd")}
    json.dump({"scanned": NOW, "count": len(items), "prices": PRICES, "items": items}, open("listings.json", "w"), separators=(",", ":"))
    status["count"] = len(items); json.dump(status, open("status.json", "w"))
    print("wrote", len(items), "items;", lookups, "detail lookups")

if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--esttest":
        for t in sys.argv[2:]: print(t, "->", llm_estimate(t))
    else:
        main()
