"""
Forge Lead Studio — Cloud Wave Auto-Expansion Engine (Agents 01 -> 05 + Cloudflare Pages Direct API)
Discovers independent residential roofing or HVAC contractors across target US metros,
audits live homepages/contact pages (disqualifying Roofr/Roofle/ScheduleEngine/NewACUnit/HVAC.com),
extracts verified contact + brand tokens, generates 01_dossier -> 02_spec -> <30 KB 03_mvp ->
<120-word CAN-SPAM 04_outreach, enforces 100/100 qa_gate.py approval, deploys live to Cloudflare
Pages via deploy_pages_api.py, and enqueues into tracking/crm_pipeline.json as QUEUED_STEP_1.
"""

import argparse
import base64
import html as html_lib
import json
import math
import os
import re
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import deploy_pages_api
import niche_evaluator

CRM_PATH = ROOT / "tracking" / "crm_pipeline.json"
PUBLIC_CRM_PATH = ROOT / "public" / "tracking" / "crm_pipeline.json"
INTEL_PATH = ROOT / "tracking" / "niche_intelligence.json"
PIPELINE_DIR = ROOT / "pipeline"
QA_SCRIPT = SCRIPT_DIR / "qa_gate.py"
TELEMETRY_ENDPOINT = "https://forge-lead-router.forge-lead-studio.workers.dev/event"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
NOMINATIM_UA = "ForgeLeadStudio-AutoExpand/1.0 (https://github.com/Jesusm1025/forge-lead-studio)"

EXCLUDED_DOMAINS = {
    "yelp.com", "angi.com", "angieslist.com", "homeadvisor.com", "thumbtack.com",
    "bbb.org", "facebook.com", "instagram.com", "linkedin.com", "youtube.com",
    "tiktok.com", "twitter.com", "x.com", "pinterest.com", "nextdoor.com",
    "mapquest.com", "yellowpages.com", "superpages.com", "houzz.com", "porch.com",
    "bark.com", "modernize.com", "networx.com", "expertise.com", "threebestrated.com",
    "wikipedia.org", "reddit.com", "forbes.com", "thisoldhouse.com", "bobvila.com",
    "homedepot.com", "lowes.com", "menards.com", "costco.com", "sears.com",
    "ars.com", "onehourheatandair.com", "serviceexperts.com", "aireserv.com",
    "goettl.com", "mrhandyman.com", "roto-rooter.com", "benjaminfranklinplumbing.com",
    "lennox.com", "trane.com", "carrier.com", "rheem.com", "goodmanmfg.com",
    "americanstandardair.com", "daikincomfort.com", "mitsubishicomfort.com",
    "gaf.com", "owenscorning.com", "certainteed.com", "iko.com", "tamko.com",
    "morscohvacsupply.com", "ferguson.com", "johnstonesupply.com", "grainger.com",
    "supplyhouse.com", "winsupplyinc.com", "bakerdist.com", "cehvac.com",
    "abcsupply.com", "becn.com", "beaconbuildingproducts.com", "srsdistribution.com",
    "marriott.com", "hilton.com", "hyatt.com", "ihg.com", "tripadvisor.com",
    "indeed.com", "glassdoor.com", "ziprecruiter.com", "manta.com", "dnb.com",
    "chamberofcommerce.com", "birdeye.com", "trustpilot.com", "google.com",
    "bing.com", "yahoo.com", "duckduckgo.com", "microsoft.com", "apple.com",
    "amazon.com", "hvac.com", "roofr.com", "roofle.com", "scheduleengine.com",
    "newacunit.com", "servicetitan.com", "housecallpro.com", "jobber.com",
    "angie.com", "buildzoom.com", "crunchbase.com", "zoominfo.com", "alignable.com",
    "citysearch.com", "foursquare.com", "hotfrog.com", "merchantcircle.com",
    "usnews.com", "consumerreports.org", "energystar.gov", "epa.gov",
    "schema.org", "w3.org", "openstreetmap.org", "gov", "edu",
}

DISQUALIFY_SIGNATURES = [
    "roofr.com", "app.roofr", "roofr-widget", "roofle", "roofquotepro",
    "instantroofer", "instant-roofer", "getroofquote", "myroofquote",
    "eagleview.com/widget", "scheduleengine", "schedule-engine",
    "newacunit", "hvac.com/calculator", "hvac.com/estimate",
    "comfortconsult", "instant-hvac-quote", "seercalculator", "estimate.hvac",
]

JUNK_EMAIL_SUBSTRINGS = [
    "noreply", "no-reply", "donotreply", "do-not-reply", "wixpress", "wix.com",
    "sentry.io", "sentry@", "wordpress", "godaddy", "example.com", "domain.com",
    "email.com", "yoursite", "yourdomain", "test@", "user@", "webmaster@",
    "privacy@", "abuse@", "postmaster@", "accessibility@", "careers@", "jobs@",
    "hr@", "billing@", "legal@", "dmca@", "press@", "media@", "mailer-daemon",
    "cloudflare", "google.com", "facebook.com", "schema.org", "w3.org",
]

BAD_EMAIL_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js", ".woff", ".woff2", ".pdf")

DEFAULT_METROS = {
    "roofing": ["Kansas City, MO", "Oklahoma City, OK", "Columbus, OH", "Indianapolis, IN"],
    "hvac": ["Houston, TX", "Austin, TX", "San Antonio, TX", "Charlotte, NC"],
}

STATE_HVAC_PRICING = {
    "AZ": (10200, 14800, 10600, 15400, 7600, 11200, 8200, 12400, "Desert High-Efficiency Heat Pump"),
    "NV": (10200, 14800, 10600, 15400, 7600, 11200, 8200, 12400, "Desert High-Efficiency Heat Pump"),
    "CA": (11000, 16200, 11500, 16800, 8200, 12000, 8800, 13400, "California High-Efficiency Heat Pump"),
    "TX": (9800, 14200, 10200, 14800, 7400, 10800, 7900, 11900, "High-Efficiency Heat Pump"),
    "FL": (9600, 13800, 9900, 14400, 7200, 10500, 7800, 11800, "Coastal High-Efficiency Heat Pump"),
    "GA": (9400, 13600, 9800, 14200, 7100, 10400, 7600, 11500, "High-Efficiency Heat Pump"),
    "NC": (9400, 13600, 9800, 14200, 7100, 10400, 7600, 11500, "High-Efficiency Heat Pump"),
    "TN": (9400, 13600, 9800, 14200, 7100, 10400, 7600, 11500, "High-Efficiency Heat Pump"),
}
DEFAULT_HVAC_PRICING = (9600, 13900, 10000, 14500, 7200, 10600, 7800, 11800, "High-Efficiency Heat Pump")

STATE_ROOF_RATES = {
    "FL": (6.25, 8.25, 13.0, 17.5, 15.0, 20.0, "Hurricane-Code Architectural Shingle", "Coastal Standing Seam Metal", "Florida Barrel & Flat Tile"),
    "TX": (5.5, 7.5, 11.5, 15.5, 13.5, 18.5, "Class 4 Hail-Rated Shingle", "Texas Standing Seam Metal", "Designer Concrete & Clay Tile"),
    "CO": (6.0, 8.0, 12.5, 16.5, 14.5, 19.5, "Class 4 Impact-Resistant Shingle", "Snow-Load Standing Seam Metal", "Architectural Slate & Tile"),
    "AZ": (5.75, 7.75, 12.0, 16.0, 14.0, 19.0, "UV-Shield Architectural Shingle", "Desert Cool-Roof Metal", "Southwest Concrete & Clay Tile"),
    "GA": (5.25, 7.25, 11.0, 15.0, 13.0, 17.5, "Wind-Rated Architectural Shingle", "Georgia Standing Seam Metal", "Architectural Slate & Tile"),
    "NC": (5.25, 7.25, 11.0, 15.0, 13.0, 17.5, "Wind-Rated Architectural Shingle", "Carolina Standing Seam Metal", "Architectural Slate & Tile"),
}
DEFAULT_ROOF_RATES = (5.5, 7.5, 11.5, 15.5, 13.5, 18.5, "Impact-Rated Architectural Shingle", "Standing Seam Metal", "Architectural Slate & Tile")


def utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def js_round(val: float) -> int:
    return int(math.floor(val + 0.5))


def calc_monthly(principal: int, apr: float = 9.99, months: int = 120) -> int:
    if apr <= 0:
        return js_round(principal / months)
    r = (apr / 100.0) / 12.0
    pmt = principal * ((r * ((1.0 + r) ** months)) / (((1.0 + r) ** months) - 1.0))
    return js_round(pmt)


def normalize_domain(url: str) -> str:
    try:
        host = urllib.parse.urlparse(url).netloc.lower().strip()
        host = host.split(":")[0]
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def is_excluded_domain(domain: str) -> bool:
    if not domain or "." not in domain:
        return True
    parts = domain.split(".")
    if parts[-1] in ("gov", "edu", "mil"):
        return True
    for i in range(len(parts) - 1):
        suffix = ".".join(parts[i:])
        if suffix in EXCLUDED_DOMAINS:
            return True
    return False


def slugify(text: str, max_len: int = 28) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    if len(s) > max_len:
        s = s[:max_len].rstrip("-")
    return s or "contractor"


def parse_metros(raw: str) -> list[tuple[str, str]]:
    if not raw or not raw.strip():
        return []
    out: list[tuple[str, str]] = []
    # Match "City Name, ST" pairs cleanly even if separated by commas or semicolons
    pairs = re.findall(r"([A-Za-z][A-Za-z .'-]+?),\s*([A-Za-z]{2})\b", raw)
    if pairs:
        for city, st in pairs:
            c = city.strip(" ,;")
            if c:
                out.append((c, st.upper()))
        return out
    # Fallback: "Houston TX, Austin TX"
    for chunk in re.split(r"[;,]+", raw):
        toks = chunk.strip().split()
        if len(toks) >= 2 and len(toks[-1]) == 2 and toks[-1].isalpha():
            out.append((" ".join(toks[:-1]), toks[-1].upper()))
    return out


def fetch_url(url: str, timeout: int = 12, max_bytes: int = 380_000) -> tuple[int, str, str]:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            final_url = resp.geturl()
            raw = resp.read(max_bytes)
            enc = resp.headers.get_content_charset() or "utf-8"
            return resp.status, final_url, raw.decode(enc, errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, url, ""
    except Exception:
        return 0, url, ""


def decode_search_href(href: str) -> str:
    if not href:
        return ""
    href = html_lib.unescape(href).strip()
    if href.startswith("//"):
        href = "https:" + href
    parsed = urllib.parse.urlparse(href)
    qs = urllib.parse.parse_qs(parsed.query)
    if "uddg" in qs and qs["uddg"]:
        return urllib.parse.unquote(qs["uddg"][0])
    # Bing click redirect: /ck/a?...&u=a1<base64url>
    if "bing.com" in parsed.netloc and "u" in qs and qs["u"]:
        u_val = qs["u"][0]
        if u_val.startswith("a1"):
            b64_part = u_val[2:]
            pad = "=" * ((4 - len(b64_part) % 4) % 4)
            try:
                decoded = base64.urlsafe_b64decode(b64_part + pad).decode("utf-8", errors="ignore")
                if decoded.startswith("http"):
                    return decoded
            except Exception:
                pass
    # Yahoo redirect: /RU=https%3a%2f%2f.../RK=
    m_ru = re.search(r"/RU=([^/]+)/R[EK]=", href)
    if m_ru:
        return urllib.parse.unquote(m_ru.group(1))
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return ""


def is_bot_challenge(body: str) -> bool:
    """Detect full-page anti-bot/block interstitials WITHOUT rejecting normal sites that include form reCAPTCHA."""
    low = body.lower()
    if any(
        sig in low
        for sig in (
            "<title>just a moment...</title>",
            "<title>attention required! | cloudflare</title>",
            "you have been blocked",
            "anomaly-modal",
            "please complete the following challenge",
            "checking if the site connection is secure",
        )
    ):
        return True
    if len(body) < 12_000 and any(
        sig in low
        for sig in ("verify you are human", "access denied", "enable javascript and cookies to continue")
    ):
        return True
    return False


def fetch_json_api(url: str, headers: dict | None = None, data: bytes | None = None, timeout: int = 12) -> tuple[int, object]:
    ctx = ssl.create_default_context()
    hdrs = {"User-Agent": NOMINATIM_UA, "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read(500_000).decode("utf-8", errors="replace")
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return 0, None


def search_optional_api(query: str) -> list[str]:
    """Tier 0: Optional free-tier Brave Search API or Serper API when env key is configured."""
    found: list[str] = []
    brave_key = (os.environ.get("BRAVE_API_KEY") or "").strip()
    if brave_key:
        u = "https://api.search.brave.com/res/v1/web/search?" + urllib.parse.urlencode({"q": query, "count": 20, "country": "US"})
        st, data = fetch_json_api(u, headers={"X-Subscription-Token": brave_key, "User-Agent": NOMINATIM_UA})
        if st == 200 and isinstance(data, dict):
            for r in ((data.get("web") or {}).get("results") or []):
                if isinstance(r, dict) and r.get("url"):
                    found.append(r["url"])
    serper_key = (os.environ.get("SERPER_API_KEY") or "").strip()
    if serper_key and len(found) < 8:
        payload = json.dumps({"q": query, "gl": "us", "num": 20}).encode("utf-8")
        st, data = fetch_json_api(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": serper_key, "Content-Type": "application/json", "User-Agent": NOMINATIM_UA},
            data=payload,
        )
        if st == 200 and isinstance(data, dict):
            for r in (data.get("organic") or []):
                if isinstance(r, dict) and r.get("link"):
                    found.append(r["link"])
    return found


def search_nominatim_metro(vertical: str, city: str, state: str) -> list[str]:
    """Tier 1 (zero-key, zero-CAPTCHA): OpenStreetMap Nominatim metro-bounded viewbox + keyword search."""
    found: list[str] = []
    seen_doms: set[str] = set()

    # 1. Geocode metro bounding box (expanded ~14 miles for suburbs)
    geo_u = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
        "q": f"{city}, {state}, USA",
        "format": "jsonv2",
        "limit": 1,
    })
    st_g, geo_data = fetch_json_api(geo_u, timeout=12)
    viewbox = ""
    if st_g == 200 and isinstance(geo_data, list) and geo_data:
        try:
            bb = [float(x) for x in geo_data[0]["boundingbox"]]  # [south, north, west, east]
            pad = 0.20
            viewbox = f"{bb[2] - pad:.4f},{bb[1] + pad:.4f},{bb[3] + pad:.4f},{bb[0] - pad:.4f}"
        except Exception:
            viewbox = ""
    time.sleep(1.05)

    terms = (
        ["roofing", "roofer", "roof repair", "roof"]
        if vertical == "roofing"
        else ["hvac", "air conditioning", "heating", "cooling", "furnace"]
    )

    # Bounded viewbox queries catch independent contractors whose OSM name omits the city
    if viewbox:
        for term in terms:
            u = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
                "q": term,
                "format": "jsonv2",
                "extratags": 1,
                "limit": 50,
                "countrycodes": "us",
                "viewbox": viewbox,
                "bounded": 1,
            })
            st, items = fetch_json_api(u, timeout=12)
            if st == 200 and isinstance(items, list):
                for it in items:
                    et = it.get("extratags") or {}
                    w = (et.get("website") or et.get("contact:website") or et.get("url") or "").strip()
                    if not w:
                        continue
                    if not w.startswith(("http://", "https://")):
                        w = "https://" + w
                    dom = normalize_domain(w)
                    if dom and dom not in seen_doms and not is_excluded_domain(dom):
                        seen_doms.add(dom)
                        found.append(f"https://{dom}/")
            time.sleep(1.05)
            if len(found) >= 24:
                break

    # Supplemental direct city+state queries if viewbox returned few hits
    if len(found) < 10:
        direct_qs = (
            [f"roofing {city} {state}", f"roofer {city} {state}"]
            if vertical == "roofing"
            else [f"hvac {city} {state}", f"air conditioning {city} {state}", f"heating {city} {state}"]
        )
        for dq in direct_qs:
            u = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
                "q": dq,
                "format": "jsonv2",
                "extratags": 1,
                "limit": 40,
                "countrycodes": "us",
            })
            st, items = fetch_json_api(u, timeout=12)
            if st == 200 and isinstance(items, list):
                for it in items:
                    et = it.get("extratags") or {}
                    w = (et.get("website") or et.get("contact:website") or et.get("url") or "").strip()
                    if not w:
                        continue
                    if not w.startswith(("http://", "https://")):
                        w = "https://" + w
                    dom = normalize_domain(w)
                    if dom and dom not in seen_doms and not is_excluded_domain(dom):
                        seen_doms.add(dom)
                        found.append(f"https://{dom}/")
            time.sleep(1.05)

    return found


def discover_candidates(vertical: str, city: str, state: str, existing_domains: set[str]) -> list[str]:
    candidates: list[str] = []
    seen = set(existing_domains)

    def _add(urls: list[str]) -> None:
        for u in urls:
            dom = normalize_domain(u)
            if dom and dom not in seen and not is_excluded_domain(dom):
                seen.add(dom)
                candidates.append(f"https://{dom}/")

    # Tier 0: Optional Brave / Serper Search API if configured in environment
    if os.environ.get("BRAVE_API_KEY") or os.environ.get("SERPER_API_KEY"):
        q = (
            f"{city} {state} residential roofing replacement contractor contact"
            if vertical == "roofing"
            else f"{city} {state} residential HVAC air conditioning replacement company contact"
        )
        _add(search_optional_api(q))

    # Tier 1: Zero-key, zero-CAPTCHA OpenStreetMap Nominatim metro-bounded discovery
    if len(candidates) < 18:
        _add(search_nominatim_metro(vertical, city, state))

    return candidates


def extract_clean_business_name(html_txt: str, domain: str) -> str:
    # 1. JSON-LD LocalBusiness / Organization name
    for m in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>', html_txt, flags=re.I):
        try:
            data = json.loads(m.group(1).strip())
            items = data if isinstance(data, list) else (data.get("@graph") if isinstance(data, dict) and "@graph" in data else [data])
            for it in items:
                if not isinstance(it, dict):
                    continue
                tp = str(it.get("@type") or "").lower()
                if any(k in tp for k in ("hvac", "roof", "homeandconstruction", "localbusiness", "organization", "contractor")):
                    nm = html_lib.unescape(str(it.get("name") or "")).strip()
                    if 3 <= len(nm) <= 58:
                        return nm
        except Exception:
            pass

    # 2. og:site_name
    m_og = re.search(r'<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)["\']', html_txt, flags=re.I)
    if m_og:
        nm = html_lib.unescape(m_og.group(1)).strip()
        if 3 <= len(nm) <= 58:
            return nm

    # 3. <title> cleaned of separators
    m_t = re.search(r"<title[^>]*>([\s\S]*?)</title>", html_txt, flags=re.I)
    if m_t:
        raw_t = re.sub(r"\s+", " ", html_lib.unescape(m_t.group(1))).strip()
        parts = [p.strip() for p in re.split(r"\s*[|\-–—•·:]\s*", raw_t) if p.strip()]
        for p in parts:
            if 3 <= len(p) <= 55 and not p.lower().startswith(("home", "welcome", "best ", "top ")):
                return p
        if parts and 3 <= len(parts[0]) <= 55:
            return parts[0]

    # Fallback: humanize apex domain
    stem = domain.split(".")[0]
    return re.sub(r"[-_]+", " ", stem).title()


def extract_email(combined_html: str, domain: str) -> str:
    decoded_html = html_lib.unescape(combined_html)
    candidates: list[str] = []
    # 1. Explicit mailto: links first
    for m in re.finditer(r'mailto:([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', decoded_html, flags=re.I):
        candidates.append(m.group(1).strip().lower())
    # 2. Visible text emails
    text_only = re.sub(r"<(script|style)[^>]*>[\s\S]*?</\1>", " ", decoded_html, flags=re.I)
    text_only = re.sub(r"<[^>]+>", " ", text_only)
    for m in re.finditer(r"\b([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b", text_only):
        candidates.append(m.group(1).strip().lower())

    valid: list[str] = []
    for em in candidates:
        if any(em.endswith(ext) for ext in BAD_EMAIL_EXTS):
            continue
        if any(bad in em for bad in JUNK_EMAIL_SUBSTRINGS):
            continue
        if len(em) > 70 or ".." in em:
            continue
        if em not in valid:
            valid.append(em)

    if not valid:
        return ""
    # Prefer same-domain email over freemail/third-party
    for em in valid:
        if em.endswith("@" + domain) or domain.split(".")[0] in em.split("@")[-1]:
            return em
    return valid[0]


def extract_phone(combined_html: str) -> str:
    # 1. tel: links first
    for m in re.finditer(r'href=["\']tel:([^"\']+)["\']', combined_html, flags=re.I):
        digits = re.sub(r"\D", "", m.group(1))
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        if len(digits) == 10 and digits[0] not in ("0", "1") and digits[:3] != "555":
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"

    # 2. Visible text regex
    text_only = re.sub(r"<(script|style)[^>]*>[\s\S]*?</\1>", " ", combined_html, flags=re.I)
    text_only = re.sub(r"<[^>]+>", " ", text_only)
    for m in re.finditer(r"(?:\+?1[\s.\-]?)?\(?([2-9]\d{2})\)?[\s.\-]+(\d{3})[\s.\-]+(\d{4})", text_only):
        a, b, c = m.groups()
        if a != "555" and f"{a}{b}{c}" not in ("1234567890", "0000000000"):
            return f"({a}) {b}-{c}"
    return ""


def extract_decision_maker(combined_html: str, business_name: str) -> tuple[str, str]:
    text = re.sub(r"<(script|style)[^>]*>[\s\S]*?</\1>", " ", combined_html, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", html_lib.unescape(text))
    patterns = [
        (r"(?:founded|owned|started)\s+by\s+([A-Z][a-z]{2,15}\s+[A-Z][a-z]{2,18})\b", "Founder & Owner"),
        (r"(?:Owner|Founder|President)\s*[:,\-–]\s*([A-Z][a-z]{2,15}\s+[A-Z][a-z]{2,18})\b", "Owner / President"),
        (r"([A-Z][a-z]{2,15}\s+[A-Z][a-z]{2,18}),\s*(?:Owner|Founder|President)\b", "Owner / President"),
    ]
    bad_first = {"Our", "The", "Your", "Free", "Best", "Call", "Contact", "About", "Home", "Air", "Roofing", "Heating", "Cooling", "Service", "Quality"}
    for pat, role in patterns:
        m = re.search(pat, text)
        if m:
            cand = m.group(1).strip()
            parts = cand.split()
            if len(parts) == 2 and parts[0] not in bad_first and parts[1] not in bad_first:
                return cand, role
    return f"{business_name} Management", "Owner / Management"


def hex_rgb(hx: str) -> tuple[int, int, int]:
    h = hx.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def hex_lum(hx: str) -> float:
    r, g, b = hex_rgb(hx)
    return 0.299 * r + 0.587 * g + 0.114 * b


def hex_sat(hx: str) -> int:
    r, g, b = hex_rgb(hx)
    return max(r, g, b) - min(r, g, b)


def extract_brand_colors(html_txt: str, vertical: str) -> tuple[str, str]:
    found: list[str] = []
    m_theme = re.search(r'<meta[^>]+name=["\']theme-color["\'][^>]+content=["\'](#[0-9a-fA-F]{3,6})["\']', html_txt, flags=re.I)
    if m_theme:
        found.append(m_theme.group(1))
    for m in re.finditer(r"--(?:primary|brand|accent|main|theme|color-primary|color-accent)[^:]*:\s*(#[0-9a-fA-F]{3,6})", html_txt, flags=re.I):
        found.append(m.group(1))
    for m in re.finditer(r"(?:background(?:-color)?|border-color)\s*:\s*(#[0-9a-fA-F]{6})\b", html_txt, flags=re.I):
        found.append(m.group(1))

    normed: list[str] = []
    for hx in found:
        h = hx.lstrip("#").upper()
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) != 6:
            continue
        full = "#" + h
        lum = hex_lum(full)
        if lum > 230 or lum < 16 or hex_sat(full) < 28:
            continue
        if full not in normed:
            normed.append(full)

    default_p, default_s = ("#0F2A47", "#D96838") if vertical == "hvac" else ("#1B2A4A", "#D97706")
    if not normed:
        return default_p, default_s
    darks = [c for c in normed if hex_lum(c) < 120]
    accents = [c for c in normed if 75 <= hex_lum(c) <= 205]
    primary = darks[0] if darks else default_p
    secondary = next((c for c in accents if c != primary), None)
    if not secondary:
        secondary = next((c for c in normed if c != primary), default_s)
    return primary, secondary


def audit_candidate_site(url: str, vertical: str, city: str, state: str) -> dict | None:
    status, final_url, home_html = fetch_url(url, timeout=12)
    if status != 200 or len(home_html) < 800 or is_bot_challenge(home_html):
        return None

    domain = normalize_domain(final_url)
    if is_excluded_domain(domain):
        return None

    low_home = home_html.lower()
    # Skip non-contractor businesses (wholesalers, supply houses, hotels, apartments)
    m_title = re.search(r"<title[^>]*>([\s\S]*?)</title>", low_home)
    title_txt = m_title.group(1) if m_title else ""
    if any(bad in title_txt for bad in ("wholesale", "supply house", "hvac supply", "roofing supply", "hotel", "apartments", "self storage")):
        return {"disqualified": True, "domain": domain, "reason": "Non-contractor / wholesale / hospitality site"}

    # Relevance gate
    if vertical == "roofing":
        if not any(k in low_home for k in ("roofing", "roof replacement", "shingle", "roofer")):
            return None
    else:
        if not any(k in low_home for k in ("hvac", "air conditioning", "heating and cooling", "furnace", "heat pump", "ac repair", "ac replacement")):
            return None

    # Disqualify existing instant calculators immediately on homepage
    for sig in DISQUALIFY_SIGNATURES:
        if sig in low_home:
            return {"disqualified": True, "domain": domain, "reason": f"Competitor widget detected on homepage ({sig})"}

    # Discover up to 3 internal contact/about/estimate links (plus standard fallbacks)
    base = f"{urllib.parse.urlparse(final_url).scheme}://{urllib.parse.urlparse(final_url).netloc}"
    extra_urls: list[str] = []
    contact_url = final_url
    for m in re.finditer(r'href=["\']([^"\']+)["\']', home_html, flags=re.I):
        href = html_lib.unescape(m.group(1)).strip()
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        abs_u = urllib.parse.urljoin(base, href)
        if normalize_domain(abs_u) != domain:
            continue
        p_low = urllib.parse.urlparse(abs_u).path.lower()
        if any(k in p_low for k in ("contact", "about", "estimate", "quote", "request")):
            if "contact" in p_low and contact_url == final_url:
                contact_url = abs_u
            if abs_u not in extra_urls and abs_u.rstrip("/") != final_url.rstrip("/"):
                extra_urls.append(abs_u)
        if len(extra_urls) >= 3:
            break

    if not any("contact" in u.lower() for u in extra_urls):
        extra_urls.append(f"{base}/contact/")
        extra_urls.append(f"{base}/contact-us/")

    combined_html = home_html
    for eu in extra_urls[:3]:
        st2, final2, html2 = fetch_url(eu, timeout=10)
        if st2 == 200 and html2:
            if "contact" in eu.lower() and contact_url == final_url:
                contact_url = final2
            low2 = html2.lower()
            for sig in DISQUALIFY_SIGNATURES:
                if sig in low2:
                    return {"disqualified": True, "domain": domain, "reason": f"Competitor widget detected on {eu} ({sig})"}
            combined_html += "\n" + html2

    email = extract_email(combined_html, domain)
    phone = extract_phone(combined_html)
    if not email or not phone:
        return {"disqualified": True, "domain": domain, "reason": f"Missing verified contact (email={bool(email)}, phone={bool(phone)})"}

    bname = extract_clean_business_name(home_html, domain)
    dm, role = extract_decision_maker(combined_html, bname)
    primary_hex, secondary_hex = extract_brand_colors(home_html, vertical)
    form_count = len(re.findall(r"<form\b", home_html, flags=re.I))

    return {
        "disqualified": False,
        "domain": domain,
        "website_url": final_url,
        "contact_page_url": contact_url,
        "business_name": bname,
        "decision_maker": dm,
        "role": role,
        "email": email,
        "phone": phone,
        "primary_hex": primary_hex,
        "secondary_hex": secondary_hex,
        "home_form_count": form_count,
        "city": city,
        "state": state,
    }


def first_name_greeting(dm: str, bname: str) -> str:
    if "management" in dm.lower() or "team" in dm.lower() or dm == "Unknown":
        return f"{bname} team"
    tok = dm.split()[0].strip(",")
    return tok if len(tok) >= 2 else f"{bname} team"


def build_and_qa_prospect(cand: dict, vertical: str) -> dict | None:
    city = cand["city"]
    state = cand["state"]
    bname = cand["business_name"]
    domain = cand["domain"]
    city_slug = slugify(city, 18)
    biz_slug = slugify(bname, 26)
    prospect_id = f"{vertical}_{city_slug}_{biz_slug}"
    pdir = PIPELINE_DIR / prospect_id
    if pdir.exists():
        biz_slug = slugify(domain.split(".")[0], 26)
        prospect_id = f"{vertical}_{city_slug}_{biz_slug}"
        pdir = PIPELINE_DIR / prospect_id
        if pdir.exists():
            return None

    now_iso = utc_iso()
    form_count = cand["home_form_count"]
    leak_desc = (
        f"Homepage has zero embedded instant quote calculator or form ({form_count} forms detected), forcing {city} mobile homeowners to call blind without a rough ballpark"
        if form_count == 0
        else f"Homepage uses a static contact form ({form_count} form{'s' if form_count != 1 else ''}) with zero instant {city} ballpark pricing or financing preview"
    )
    proj_slug = (
        (f"{biz_slug}-demo" if biz_slug.endswith("-hvac") else f"{biz_slug}-hvac-demo")
        if vertical == "hvac"
        else f"{biz_slug}-demo"
    )

    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "03_mvp").mkdir(exist_ok=True)
    (pdir / "04_outreach").mkdir(exist_ok=True)

    try:
        # 1. Stage 01 Dossier + Audit Notes
        dossier = {
            "prospect_id": prospect_id,
            "scouted_at": now_iso,
            "niche": vertical,
            "business_name": bname,
            "location": {"city": city, "state": state, "country": "US"},
            "website_url": cand["website_url"],
            "contact_info": {
                "decision_maker": cand["decision_maker"],
                "role": cand["role"],
                "email": cand["email"],
                "phone": cand["phone"],
                "contact_page_url": cand["contact_page_url"],
            },
            "brand_tokens": {
                "primary_color_hex": cand["primary_hex"],
                "secondary_color_hex": cand["secondary_hex"],
                "brand_vibe": f"Independent {city} {vertical.upper() if vertical == 'hvac' else 'roofing'} contractor focused on local trust",
            },
            "technical_audit": {
                "has_instant_quote_tool": False,
                "mobile_ux_issues": [
                    leak_desc,
                    f"Mobile homeowners in {city}, {state} comparing replacement options have no 30-second financing preview before dialing {cand['phone']}",
                ],
                "seo_or_speed_leaks": [
                    f"No interactive instant replacement ballpark calculator on {domain} to capture high-intent after-hours traffic",
                    "Replacement shoppers bounce to national lead aggregators when zero upfront pricing guidance is visible",
                ],
                "current_lead_capture_method": f"Click-to-call phone ({cand['phone']}) and static contact form with zero upfront pricing range",
            },
            "trojan_horse_angle": {
                "recommended_solution": "TYPE_B_HVAC_CALCULATOR" if vertical == "hvac" else "TYPE_A_ROOFING_CALCULATOR",
                "pitch_hook_english": f"{domain} has no instant replacement ballpark widget — forcing {city} homeowners to call blind without a rough range.",
                "proposed_setup_fee_usd": 750,
                "proposed_retainer_usd": 149,
            },
        }
        (pdir / "01_dossier.json").write_text(json.dumps(dossier, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (pdir / "01_audit_notes.md").write_text(
            f"# Agent 01 Live Audit — {bname} ({city}, {state})\n\n"
            f"- **Website:** {cand['website_url']}\n"
            f"- **Contact:** {cand['decision_maker']} ({cand['role']}) · `{cand['email']}` · `{cand['phone']}`\n"
            f"- **Brand Tokens:** Primary `{cand['primary_hex']}` · Secondary `{cand['secondary_hex']}`\n"
            f"- **Instant Quote Calculator:** None verified (disqualification scan clean)\n"
            f"- **Observed Leak:** {leak_desc}\n",
            encoding="utf-8",
        )

        # 2. Stage 02 Spec + Exact Baseline Math
        if vertical == "hvac":
            ac_min, ac_max, hp_min, hp_max, coil_min, coil_max, mini_min, mini_max, hp_lbl = STATE_HVAC_PRICING.get(state, DEFAULT_HVAC_PRICING)
            base_min = js_round(ac_min / 100.0) * 100
            base_max = js_round(ac_max / 100.0) * 100
            base_mo = calc_monthly(base_min, 9.99, 120)
            spec = {
                "prospect_id": prospect_id,
                "architected_at": now_iso,
                "template_base": "hvac-quote-calc",
                "vertical": "hvac",
                "telemetry_endpoint": TELEMETRY_ENDPOINT,
                "delivery_mode": "demo",
                "brand_config": {
                    "business_name": bname,
                    "tagline": f"{city} Residential HVAC Replacement & Comfort Specialists",
                    "primary_hex": cand["primary_hex"],
                    "secondary_hex": cand["secondary_hex"],
                    "surface_hex": "#F8FAFC",
                    "text_hex": "#132238",
                    "cta_label": f"Schedule Free {city} HVAC Estimate",
                    "phone_display": cand["phone"],
                },
                "pricing_engine": {
                    "currency": "USD",
                    "base_system_prices": {
                        "ac_gas_furnace": {"min": ac_min, "max": ac_max, "label": "Central AC + Gas Furnace"},
                        "heat_pump": {"min": hp_min, "max": hp_max, "label": hp_lbl},
                        "ac_coil_only": {"min": coil_min, "max": coil_max, "label": "AC Condenser & Coil Only"},
                        "ductless_minisplit": {"min": mini_min, "max": mini_max, "label": "Ductless Mini-Split System"},
                    },
                    "tonnage_multipliers": {"under_1500": 0.85, "1500_2200": 1.0, "2200_3000": 1.18, "over_3000": 1.42},
                    "seer2_multipliers": {"standard_seer2": 0.88, "high_seer2": 1.0, "variable_seer2": 1.24},
                    "ductwork_adder": {"min": 1800, "max": 3200},
                    "financing_apr_percent": 9.99,
                    "financing_term_months": 120,
                },
                "ux_steps": [
                    {"step_number": 1, "title": "Home Square Footage & Tonnage Sizing", "inputs": ["< 1,500 sq ft", "1,500–2,200 sq ft", "2,200–3,000 sq ft", "3,000+ sq ft"], "conversion_psychology_note": "Single-tap sizing brackets anchor tonnage in 5 seconds."},
                    {"step_number": 2, "title": "HVAC System Type Selection", "inputs": ["Central AC + Gas Furnace", "High-Efficiency Heat Pump", "AC Condenser & Coil Only", "Ductless Mini-Split System"], "conversion_psychology_note": "Clear equipment cards pre-qualify replacement scope upfront."},
                    {"step_number": 3, "title": "SEER2 Efficiency Tier & Ductwork", "inputs": ["14.3–15.2 SEER2", "16–18 SEER2", "19+ SEER2", "Ductwork Status"], "conversion_psychology_note": "Educates homeowners on federal 25C rebates and inverter upsells."},
                    {"step_number": 4, "title": "Ungated Ballpark & 3-Field Lead Capture", "inputs": ["Installed Range", "Full Name", "Phone or Email", "Street Address"], "conversion_psychology_note": "Honest local pricing upfront drives higher booked in-home load checks."},
                ],
                "preview_wrapper_spec": {
                    "hero_headline": f"Get Your Instant {city} HVAC Replacement & SEER2 Financing Ballpark in 30 Seconds",
                    "hero_subheadline": f"Built in {bname}'s exact brand colors: converts {city}, {state} mobile shoppers into pre-qualified replacement bookings without rebuilding {domain}.",
                    "pain_points_solved_callouts": [
                        leak_desc,
                        "Captures home tonnage, system type, SEER2 tier, ductwork status, and street address before your advisor dials",
                        f"Self-contained <30 KB Shadow DOM script — drops onto {domain} with one line of code in 5 minutes",
                    ],
                },
                "commercial_offer": {
                    "setup_fee_usd": 750,
                    "monthly_retainer_usd": 149,
                    "retainer_deliverables": [
                        "Managed Cloudflare edge hosting & <30 KB Shadow DOM widget updates",
                        "Direct email/SMS/CRM webhook lead routing with full tonnage, SEER2 & street address payload",
                        f"Quarterly {city}, {state} equipment, SEER2 & financing rate updates",
                    ],
                },
            }
            hydrate_script = ROOT / "templates" / "hvac-quote-calc" / "hydrate.py"
        else:
            s_min, s_max, m_min, m_max, t_min, t_max, s_lbl, m_lbl, t_lbl = STATE_ROOF_RATES.get(state, DEFAULT_ROOF_RATES)
            base_min = js_round((2400 * s_min) / 100.0) * 100
            base_max = js_round((2400 * s_max) / 100.0) * 100
            base_mo = calc_monthly(base_min, 9.99, 120)
            spec = {
                "prospect_id": prospect_id,
                "architected_at": now_iso,
                "template_base": "roofing-quote-calc",
                "vertical": "roofing",
                "telemetry_endpoint": TELEMETRY_ENDPOINT,
                "delivery_mode": "demo",
                "brand_config": {
                    "business_name": bname,
                    "tagline": f"{city} Roof Replacement & Storm Restoration Specialists",
                    "primary_hex": cand["primary_hex"],
                    "secondary_hex": cand["secondary_hex"],
                    "surface_hex": "#F8FAFC",
                    "text_hex": "#172033",
                    "cta_label": f"Schedule Free {city} Roof Inspection",
                    "phone_display": cand["phone"],
                },
                "pricing_engine": {
                    "currency": "USD",
                    "base_rates_per_sqft": {
                        "architectural_shingle": {"min": s_min, "max": s_max, "label": s_lbl},
                        "standing_seam_metal": {"min": m_min, "max": m_max, "label": m_lbl},
                        "designer_tile": {"min": t_min, "max": t_max, "label": t_lbl},
                    },
                    "story_multipliers": {"one_story": 1.0, "two_story": 1.12, "three_plus": 1.25},
                    "pitch_multipliers": {"low": 0.95, "standard": 1.0, "steep": 1.18},
                    "financing_apr_percent": 9.99,
                    "financing_term_months": 120,
                },
                "ux_steps": [
                    {"step_number": 1, "title": "Property Profile", "inputs": ["Footprint slider (1,200–4,500 sq ft)", "Stories selector"], "conversion_psychology_note": "Visual slider engages homeowners in 5 seconds."},
                    {"step_number": 2, "title": "Roof Pitch & Storm Condition", "inputs": ["Slope selector", "Routine / Storm / Leak"], "conversion_psychology_note": "Separates urgent storm inspections from routine replacements."},
                    {"step_number": 3, "title": f"Select {city} Roofing System", "inputs": [s_lbl, m_lbl, t_lbl], "conversion_psychology_note": "Pre-educates homeowners on local installed material tiers."},
                    {"step_number": 4, "title": "Instant Ballpark & 2-Field Booking", "inputs": [f"Range (${base_min:,}–${base_max:,})", "Full Name", "Phone or Email"], "conversion_psychology_note": "Transparent local range before asking for contact lifts conversion."},
                ],
                "preview_wrapper_spec": {
                    "hero_headline": f"Get Your Instant {city} Roof Replacement & Financing Ballpark in 30 Seconds",
                    "hero_subheadline": f"Built in {bname}'s exact brand colors: turns {city}, {state} mobile visitors into pre-qualified inspection bookings without rebuilding {domain}.",
                    "pain_points_solved_callouts": [
                        leak_desc,
                        "Automatically captures roof sq. ft., stories, slope, material preference, and storm urgency before your team dials",
                        f"Self-contained <30 KB Shadow DOM script — drops onto {domain} with one line of code in 5 minutes",
                    ],
                },
                "commercial_offer": {
                    "setup_fee_usd": 750,
                    "monthly_retainer_usd": 149,
                    "retainer_deliverables": [
                        "Global Cloudflare edge hosting & <30 KB Shadow DOM widget updates",
                        "Instant email/SMS/CRM webhook lead routing with full roof specs and storm urgency",
                        f"Quarterly {city}, {state} material and labor pricing calibration",
                    ],
                },
            }
            hydrate_script = ROOT / "templates" / "roofing-quote-calc" / "hydrate.py"

        spec_path = pdir / "02_spec.json"
        spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        # 3. Stage 03 Hydrate (<30 KB Shadow DOM MVP)
        mvp_dir = pdir / "03_mvp"
        h_res = subprocess.run(
            [sys.executable, str(hydrate_script), str(spec_path), str(mvp_dir)],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        if h_res.returncode != 0:
            raise RuntimeError(f"Hydrate failed: {h_res.stderr or h_res.stdout}")

        # Ensure live Cloudflare Pages embed URL in index.html for roofing too
        idx_path = mvp_dir / "index.html"
        idx_txt = idx_path.read_text(encoding="utf-8")
        idx_txt = re.sub(
            r"https://widgets\.trojanagency\.com/[^\"'<>\s]+/widget\.js",
            f"https://{proj_slug}.pages.dev/widget.js",
            idx_txt,
        )
        idx_path.write_text(idx_txt, encoding="utf-8")

        # 4. Stage 04 CAN-SPAM <120-word Outreach Sequence
        greet = first_name_greeting(cand["decision_maker"], bname)
        range_str = f"${base_min:,}–${base_max:,}"
        mo_str = f"${base_mo:,}/mo"
        short_biz = bname[:36].strip()
        if vertical == "hvac":
            e1_body = (
                f"Hey {greet},\n\n"
                f"I was reviewing {domain} — great reputation serving {city} homeowners.\n\n"
                f"One mobile leak stood out: {domain} has no instant HVAC replacement ballpark, so after-hours shoppers leave before calling.\n\n"
                f"I built a working 30-second {city} HVAC Estimator in {bname}'s brand colors. Homeowners pick home size, system type, SEER2 tier, and ductwork for an instant local range before leaving their name, phone, and address.\n\n"
                f"Mind if I send the live preview link?\n\n"
                f"— {{{{sender_name}}}}\n\n{{{{sender_address}}}} | {{{{unsubscribe_line}}}}"
            )
            e2_body = (
                f"Hey {greet},\n\n"
                f"Here is the working {city} HVAC replacement prototype I built for {bname}:\n\n"
                f"Live demo: {{{{preview_url}}}}\n60-sec video: {{{{loom_url}}}}\n\n"
                f"It is calibrated for {city} installs (a 3–3.5 ton 16–18 SEER2 system prices at {range_str}, from {mo_str}), captures full specs plus street address, and drops onto {domain} with one line of code in 5 minutes — zero redesign.\n\n"
                f"Want to put it live this week?\n\n"
                f"— {{{{sender_name}}}}\n\n{{{{sender_address}}}} | {{{{unsubscribe_line}}}}"
            )
            e3_body = (
                f"Hey {greet},\n\n"
                f"Homeowners shopping a {range_str} AC or heat pump upgrade after hours hate calling blind, so most bounce to national directories.\n\n"
                f"Your {bname} calculator ({{{{preview_url}}}}) shows a transparent SEER2 ballpark and {mo_str} financing preview in 30 seconds — then routes tonnage, system choice, and address straight to your dispatch team.\n\n"
                f"One extra system changeout pays for the $750 setup and $149/mo hosting 10x over. Open to a quick 10-minute look?\n\n"
                f"— {{{{sender_name}}}}\n\n{{{{sender_address}}}} | {{{{unsubscribe_line}}}}"
            )
            e4_body = (
                f"Hey {greet},\n\n"
                f"I know {city} dispatch boards stay packed, so I will keep this short.\n\n"
                f"I will leave your branded {bname} HVAC estimator live here a few more days: {{{{preview_url}}}}\n\n"
                f"If adding instant SEER2 ballpark quotes to {domain} ever makes sense, just reply \"yes\" and we will install it in 5 minutes.\n\n"
                f"— {{{{sender_name}}}}\n\n{{{{sender_address}}}} | {{{{unsubscribe_line}}}}"
            )
            s1a, s1b = f"Quick HVAC build for {short_biz}", f"Instant SEER2 estimator for {domain[:36]}"
            s2a, s2b = f"Your {short_biz} HVAC demo", f"Live preview: {city} HVAC quote widget"
            s3a, s3b = f"Capturing after-hours {city} AC installs", "1 replacement pays for your quote tool 10x"
            s4a, s4b = f"Leaving your {short_biz} demo live", f"Keep your {city} HVAC preview live?"
            ln_note = f"Hey {greet}, noticed {domain} has no instant {city} HVAC ballpark for mobile shoppers, so I built a working <30KB SEER2 estimator in your colors. Happy to share the link."[:275]
        else:
            e1_body = (
                f"Hey {greet},\n\n"
                f"I was reviewing {domain} — great reputation serving {city} homeowners.\n\n"
                f"One mobile leak stood out: {domain} has no instant roof replacement ballpark, so after-hours homeowners bounce before calling.\n\n"
                f"I built a working 30-second {city} Roof Estimator in {bname}'s brand colors. Visitors pick roof size, stories, slope, and shingle/metal/tile for an instant local range before booking their inspection.\n\n"
                f"Mind if I send the live preview link?\n\n"
                f"— {{{{sender_name}}}}\n\n{{{{sender_address}}}} | {{{{unsubscribe_line}}}}"
            )
            e2_body = (
                f"Hey {greet},\n\n"
                f"Here is the working {city} roof replacement prototype I built for {bname}:\n\n"
                f"Live demo: {{{{preview_url}}}}\n60-sec video: {{{{loom_url}}}}\n\n"
                f"It is calibrated for {city} rates (a 2,400 sq ft 1-story shingle roof prices at {range_str}, from {mo_str}), flags storm/leak urgency automatically, and drops onto {domain} with one line of code in 5 minutes — zero redesign.\n\n"
                f"Want to put it live this week?\n\n"
                f"— {{{{sender_name}}}}\n\n{{{{sender_address}}}} | {{{{unsubscribe_line}}}}"
            )
            e3_body = (
                f"Hey {greet},\n\n"
                f"Homeowners researching a {range_str} roof replacement after hours hate filling long contact forms with zero pricing guidance.\n\n"
                f"Your {bname} calculator ({{{{preview_url}}}}) shows a transparent local ballpark and {mo_str} financing preview in 30 seconds — then routes full roof specs and storm urgency straight to your inbox.\n\n"
                f"One extra roof replacement pays for the $750 setup and $149/mo hosting 15x over. Open to a quick 10-minute look?\n\n"
                f"— {{{{sender_name}}}}\n\n{{{{sender_address}}}} | {{{{unsubscribe_line}}}}"
            )
            e4_body = (
                f"Hey {greet},\n\n"
                f"I know roofing crews across {city} stay slammed, so I will keep this brief.\n\n"
                f"I will leave your branded {bname} roof estimator live here a few more days: {{{{preview_url}}}}\n\n"
                f"If adding instant roof ballpark quotes to {domain} ever makes sense, just reply \"yes\" and we will install it in 5 minutes.\n\n"
                f"— {{{{sender_name}}}}\n\n{{{{sender_address}}}} | {{{{unsubscribe_line}}}}"
            )
            s1a, s1b = f"Quick build for {short_biz}", f"Instant roof quote widget for {domain[:36]}"
            s2a, s2b = f"Your {short_biz} roof demo", f"Live preview: {city} roof quote widget"
            s3a, s3b = f"Capturing after-hours {city} roof leads", "1 roof replacement pays for this 15x"
            s4a, s4b = f"Leaving your {short_biz} demo live", f"Keep your {city} roof preview live?"
            ln_note = f"Hey {greet}, noticed {domain} has no instant {city} roof ballpark for mobile shoppers, so I built a working <30KB estimator in your colors. Happy to send the preview link."[:275]

        emails = [
            {"step": 1, "delay_days": 0, "subject_line_a": s1a[:72], "subject_line_b": s1b[:72], "body_text": e1_body, "word_count": len(e1_body.split()), "psychological_trigger": "Reciprocity + permission-based value-first hook"},
            {"step": 2, "delay_days": 3, "subject_line_a": s2a[:72], "subject_line_b": s2b[:72], "body_text": e2_body, "word_count": len(e2_body.split()), "psychological_trigger": "Tangible proof + zero-redesign friction removal"},
            {"step": 3, "delay_days": 7, "subject_line_a": s3a[:72], "subject_line_b": s3b[:72], "body_text": e3_body, "word_count": len(e3_body.split()), "psychological_trigger": "Asymmetric ROI anchor ($750 setup vs $10k+ job)"},
            {"step": 4, "delay_days": 12, "subject_line_a": s4a[:72], "subject_line_b": s4b[:72], "body_text": e4_body, "word_count": len(e4_body.split()), "psychological_trigger": "Zero-pressure takeaway close"},
        ]

        seq = {
            "prospect_id": prospect_id,
            "generated_at": now_iso,
            "target_recipients": [f"{cand['decision_maker']} <{cand['email']}>"],
            "primary_channel": "cold_email",
            "emails": emails,
            "linkedin_dm_touch": {
                "connection_note": ln_note,
                "follow_up_dm": f"Thanks for connecting! Here is the working {city} prototype built for {bname}: {{{{preview_url}}}} — installs on {domain} in 5 minutes with zero redesign.",
            },
            "loom_60s_script": {
                "hook_0_15s": f"Open {cand['website_url']} on mobile and show the missing instant {city} replacement ballpark.",
                "pain_comparison_15_35s": f"Contrast {domain}'s static lead capture with mobile shoppers expecting a 30-second local range and monthly payment preview.",
                "live_demo_walkthrough_35_50s": f"Walk through Steps 1–4 on live {{{{preview_url}}}} ({range_str}, from {mo_str}) and submit a sample lead.",
                "zero_pressure_cta_50_60s": f"Show the structured trojan:lead_captured webhook payload and invite {greet} to install the 1-line <30 KB script for $750 setup + $149/mo.",
            },
            "objection_handlers": [
                {"objection": "We do not want to quote exact prices without an on-site visit.", "reframe_response": f"Agreed — the widget displays a realistic {city} ballpark range ({range_str}) with an on-site inspection disclaimer so tire-kickers self-filter."},
                {"objection": "We already use our own CRM or contact form.", "reframe_response": "It drops right alongside your existing stack and emits a clean JSON webhook directly to your dispatch inbox, SMS, or CRM."},
                {"objection": "Will a calculator slow down our site or break our layout?", "reframe_response": "Zero external libraries and under 30 KB of pure Shadow DOM vanilla JS — installs with one script tag in 5 minutes with zero CSS conflicts."},
                {"objection": "Why is there a $149/mo retainer after the $750 setup?", "reframe_response": "Covers global Cloudflare edge hosting, instant lead routing uptime, and quarterly regional pricing updates — a single booked job pays for years of it."},
            ],
        }
        (pdir / "04_outreach" / "sequence.json").write_text(json.dumps(seq, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (pdir / "04_outreach" / "copy_pack.md").write_text(
            f"# Outreach Copy Pack — {bname} ({city}, {state})\n\n"
            + "\n\n".join(f"## Step {e['step']} (Day +{e['delay_days']}) — {e['subject_line_a']}\n\n{e['body_text']}" for e in emails)
            + "\n",
            encoding="utf-8",
        )
        (pdir / "04_outreach" / "objections.md").write_text(
            f"# Objection Playbook — {bname}\n\n"
            + "\n\n".join(f"### {o['objection']}\n{o['reframe_response']}" for o in seq["objection_handlers"])
            + "\n",
            encoding="utf-8",
        )

        # 5. Stage 05 Strict QA Gate (100/100 APPROVED required)
        qa_res = subprocess.run(
            [sys.executable, str(QA_SCRIPT), prospect_id],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        audit_path = pdir / "05_qa_audit.json"
        if qa_res.returncode != 0 or not audit_path.exists():
            raise RuntimeError(f"QA Gate rejected {prospect_id}: {(qa_res.stderr or qa_res.stdout).strip()[:300]}")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        if audit.get("verdict") != "APPROVED" or int(audit.get("overall_score_100") or 0) != 100:
            raise RuntimeError(f"QA Gate score < 100 for {prospect_id}: {audit.get('verdict')} {audit.get('overall_score_100')}")

        w_bytes = (mvp_dir / "widget.js").stat().st_size
        return {
            "prospect_id": prospect_id,
            "vertical": vertical,
            "proj_slug": proj_slug,
            "pdir": pdir,
            "mvp_dir": mvp_dir,
            "dossier": dossier,
            "spec": spec,
            "qa_score": 100,
            "widget_bytes": w_bytes,
            "baseline_range": f"{range_str} ({mo_str})",
            "word_counts": [e["word_count"] for e in emails],
        }
    except Exception as ex:
        shutil.rmtree(pdir, ignore_errors=True)
        print(f"  [QA-SKIP] {bname} ({domain}): {ex}", flush=True)
        return None


def determine_expansion_jobs(args, crm: dict, intel: dict) -> list[tuple[str, int, list[tuple[str, str]]]]:
    prospects = crm.get("prospects") or []
    jobs: list[tuple[str, int, list[tuple[str, str]]]] = []

    if args.auto or args.vertical == "auto":
        verticals = intel.get("verticals") or {}
        for v_key, v_info in verticals.items():
            if v_key not in ("roofing", "hvac"):
                continue
            if v_info.get("verdict") != "SCALE":
                continue
            queued_cnt = sum(
                1 for p in prospects
                if niche_evaluator.infer_vertical(p) == v_key and str(p.get("status") or "").upper() == "QUEUED_STEP_1"
            )
            if queued_cnt >= 12:
                print(f"[AUTO-SKIP] {v_key.upper()} is SCALE but already has {queued_cnt} QUEUED_STEP_1 prospects (>=12).", flush=True)
                continue
            needed = max(1, min(args.count, 12 - queued_cnt))
            raw_metros = ((v_info.get("recommendation") or {}).get("en") or {}).get("target_metros") or DEFAULT_METROS[v_key]
            metros = parse_metros("; ".join(raw_metros))
            jobs.append((v_key, needed, metros))
        return jobs

    v_key = args.vertical.lower()
    if args.metros:
        metros = parse_metros(args.metros)
    else:
        v_info = (intel.get("verticals") or {}).get(v_key) or {}
        raw_metros = ((v_info.get("recommendation") or {}).get("en") or {}).get("target_metros") or DEFAULT_METROS[v_key]
        metros = parse_metros("; ".join(raw_metros))
    if not metros:
        metros = parse_metros("; ".join(DEFAULT_METROS[v_key]))
    jobs.append((v_key, max(1, min(12, args.count)), metros))
    return jobs


def main() -> int:
    parser = argparse.ArgumentParser(description="Forge Lead Studio — Cloud Wave Auto-Expansion Engine")
    parser.add_argument("--auto", action="store_true", help="Auto-expand any vertical in SCALE verdict with <12 QUEUED_STEP_1 prospects")
    parser.add_argument("--vertical", choices=["auto", "roofing", "hvac"], default="auto", help="Target vertical for manual wave expansion")
    parser.add_argument("--count", type=int, default=12, help="Number of new prospects to build & deploy (1..12)")
    parser.add_argument("--metros", default="", help='Optional target metros (e.g. "Houston, TX; Austin, TX")')
    parser.add_argument("--dry-run", action="store_true", help="Run live discovery, crawl, QA 100/100, and deployer dry-run without mutating CRM or deploying live")
    args = parser.parse_args()

    crm = json.loads(CRM_PATH.read_text(encoding="utf-8"))
    intel = json.loads(INTEL_PATH.read_text(encoding="utf-8")) if INTEL_PATH.exists() else niche_evaluator.evaluate_niches(crm_data=crm, write_files=False)

    jobs = determine_expansion_jobs(args, crm, intel)
    if not jobs:
        verdicts_str = ", ".join(f"{k}={v.get('verdict')}" for k, v in (intel.get("verticals") or {}).items())
        print(f"[AUTO-SKIP] No vertical eligible for auto-expansion right now ({verdicts_str or 'none'}). Exiting 0.", flush=True)
        return 0

    existing_domains = {normalize_domain(p.get("website_url") or "") for p in crm.get("prospects", [])}
    existing_domains.discard("")

    created_records: list[dict] = []
    temp_dirs_to_clean: list[Path] = []

    try:
        for vertical, target_count, metros in jobs:
            print(f"\n[EXPAND] Vertical={vertical.upper()} | Target={target_count} | Mode={'DRY-RUN' if args.dry_run else 'LIVE'} | Metros={metros}", flush=True)
            built_for_vertical = 0

            for city, state in metros:
                if built_for_vertical >= target_count:
                    break
                print(f"\n  [SCOUT] Searching {city}, {state} ({vertical})...", flush=True)
                urls = discover_candidates(vertical, city, state, existing_domains)
                print(f"  [SCOUT] Found {len(urls)} candidate domains in {city}, {state}.", flush=True)

                for u in urls:
                    if built_for_vertical >= target_count:
                        break
                    dom = normalize_domain(u)
                    if dom in existing_domains:
                        continue
                    cand = audit_candidate_site(u, vertical, city, state)
                    if not cand:
                        continue
                    if cand.get("disqualified"):
                        print(f"    [SKIP] {cand['domain']}: {cand['reason']}", flush=True)
                        existing_domains.add(cand["domain"])
                        continue

                    existing_domains.add(cand["domain"])
                    print(f"    [QUALIFIED] {cand['business_name']} ({cand['domain']}) · {cand['email']} · {cand['phone']} · {cand['primary_hex']}/{cand['secondary_hex']}", flush=True)
                    built = build_and_qa_prospect(cand, vertical)
                    if not built:
                        continue

                    if args.dry_run:
                        temp_dirs_to_clean.append(built["pdir"])

                    dep = deploy_pages_api.deploy_static_site(
                        project_name=built["proj_slug"],
                        source_dir=built["mvp_dir"],
                        dry_run=args.dry_run,
                        verify=not args.dry_run,
                    )
                    if not args.dry_run:
                        ver = dep.get("verification") or {}
                        if ver.get("root_status") != 200 or ver.get("widget_status") != 200:
                            print(f"    [DEPLOY-WARN] {built['proj_slug']} live check returned {ver}; skipping CRM enqueue.", flush=True)
                            shutil.rmtree(built["pdir"], ignore_errors=True)
                            continue

                    now_ts = utc_iso()
                    wave_lbl = f"{'HVAC ' if vertical == 'hvac' else ''}Cloud Wave {utc_date()}"
                    crm_entry = {
                        "prospect_id": built["prospect_id"],
                        "business_name": built["dossier"]["business_name"],
                        "niche": vertical,
                        "vertical": vertical,
                        "city": city,
                        "state": state,
                        "country": "US",
                        "website_url": built["dossier"]["website_url"],
                        "decision_maker": built["dossier"]["contact_info"]["decision_maker"],
                        "email": built["dossier"]["contact_info"]["email"],
                        "phone": built["dossier"]["contact_info"]["phone"],
                        "primary_color_hex": built["dossier"]["brand_tokens"]["primary_color_hex"],
                        "recommended_solution": built["dossier"]["trojan_horse_angle"]["recommended_solution"],
                        "proposed_setup_fee_usd": 750,
                        "proposed_retainer_usd": 149,
                        "status": "QUEUED_STEP_1",
                        "wave": wave_lbl,
                        "dossier_path": f"pipeline/{built['prospect_id']}/01_dossier.json",
                        "spec_path": f"pipeline/{built['prospect_id']}/02_spec.json",
                        "mvp_dir": f"pipeline/{built['prospect_id']}/03_mvp",
                        "outreach_dir": f"pipeline/{built['prospect_id']}/04_outreach",
                        "widget_bytes": built["widget_bytes"],
                        "telemetry_enabled": True,
                        "scouted_at": now_ts,
                        "architected_at": now_ts,
                        "built_at": now_ts,
                        "outreach_generated_at": now_ts,
                        "qa_verdict": "APPROVED",
                        "qa_score": 100,
                        "cloudflare_project": built["proj_slug"],
                        "deployment_id": dep.get("deployment_id") or "dry-run",
                        "live_preview_url": dep.get("live_url"),
                        "live_widget_url": dep.get("live_widget_url"),
                        "deployed_at": dep.get("deployed_at") or now_ts,
                        "outreach_history": [],
                        "demo_views": 0,
                        "max_step_reached": 0,
                        "test_leads": 0,
                        "prod_leads": 0,
                    }
                    created_records.append(crm_entry)
                    built_for_vertical += 1
                    print(
                        f"    [PASS 100/100] {built['prospect_id']} | widget={built['widget_bytes']} B | "
                        f"WCs={built['word_counts']} | range={built['baseline_range']} | url={dep.get('live_url')} ({'DRY-RUN' if args.dry_run else 'LIVE'})",
                        flush=True,
                    )

        if not args.dry_run and created_records:
            crm["prospects"].extend(created_records)
            crm["updated_at"] = utc_iso()
            CRM_PATH.write_text(json.dumps(crm, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            PUBLIC_CRM_PATH.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(CRM_PATH, PUBLIC_CRM_PATH)
            niche_evaluator.evaluate_niches(crm_data=crm, write_files=True)
            print(f"\n[SAVED] Enqueued {len(created_records)} new QUEUED_STEP_1 prospects into CRM + refreshed Agent 00 intel.", flush=True)
        else:
            print(f"\n[SUMMARY] Mode={'DRY-RUN' if args.dry_run else 'LIVE'} | Qualified & QA-Approved={len(created_records)}", flush=True)

        return 0
    finally:
        for td in temp_dirs_to_clean:
            shutil.rmtree(td, ignore_errors=True)
        if temp_dirs_to_clean:
            print(f"[DRY-RUN CLEANUP] Removed {len(temp_dirs_to_clean)} temporary dry-run prospect directories; repo & CRM unchanged.", flush=True)


if __name__ == "__main__":
    sys.exit(main())
