"""Live web checks. Each check asks SerpApi one question about the company and
turns the answer into a signal (red / amber / green), a score delta and evidence links."""
import re
from dataclasses import asdict, dataclass, field
from urllib.parse import urlparse

import requests

import serp
from analyzer import FREE_MAIL_DOMAINS

SCAM_WORDS = re.compile(r"\b(scam|scammer|fraud|fake|cheat(ed|ing)?|beware|complaint|not\s+legit|ponzi)\b", re.I)

# Sites that mention a company but are not the company's own website.
NOT_OFFICIAL = (
    "linkedin.", "facebook.", "instagram.", "twitter.", "x.com", "youtube.", "glassdoor.",
    "ambitionbox.", "indeed.", "naukri.", "internshala.", "justdial.", "zaubacorp.", "tofler.",
    "crunchbase.", "wikipedia.", "quora.", "reddit.", "medium.", "unstop.", "tracxn.", "apollo.io",
    "zoominfo.", "rocketreach.", "falconebiz.", "thecompanycheck.", "instafinancials.", "google.",
    "foundit.", "shine.", "wellfound.", "ycombinator.", "github.", "play.google.", "apps.apple.",
)


@dataclass
class CheckResult:
    id: str
    title: str
    engine: str
    signal: str = "neutral"  # red | amber | green | neutral | error
    delta: int = 0
    summary: str = ""
    evidence: list = field(default_factory=list)
    cached: bool = False
    results: int = 0  # how many search results this check read
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("data", None)
        return d


REGISTRY_SITES = ("zaubacorp.com", "tofler.in", "thecompanycheck.com", "instafinancials.com", "falconebiz.com")
POSITIVE_CONTEXT = re.compile(r"\b(prevent|prevents|preventing|detect|detection|fight|fights|against|tackle|"
                              r"protect|security|secure|safety|awareness|alert|warns?|launch(es|ed)?)\b", re.I)


def _domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _root(host: str) -> str:
    """sales.razorpay.com -> razorpay.com, abc.co.in -> abc.co.in"""
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in ("co", "org", "net", "ac", "gov", "com") and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _tokens(company: str) -> list[str]:
    generic = {"pvt", "ltd", "private", "limited", "technologies", "technology", "solutions",
               "labs", "infotech", "systems", "software", "services", "india", "inc", "llp", "the",
               "global", "consultancy", "consulting", "ventures", "corp", "corporation"}
    words = re.findall(r"[a-z0-9]+", company.lower())
    core = [w for w in words if w not in generic and len(w) > 1]
    return core or words


def _mentions(company: str, text: str) -> bool:
    text = text.lower()
    return all(t in text for t in _tokens(company)[:2])


def _ev(title: str, link: str, snippet: str = "", source: str = "") -> dict:
    return {"title": title, "link": link, "snippet": snippet, "source": source}


def _run(result: CheckResult, params: dict) -> dict | None:
    try:
        data, cached = serp.search(params)
    except serp.SerpApiError as exc:
        result.signal, result.summary = "error", str(exc)
        return None
    result.cached = cached
    for key in ("organic_results", "local_results", "news_results", "jobs_results"):
        result.results += len(data.get(key) or [])
    return data


def check_website(company: str) -> CheckResult:
    r = CheckResult("website", "Official website", "Google Search")
    data = _run(r, {"engine": "google", "q": f'"{company}" official website', "gl": "in", "hl": "en"})
    if data is None:
        return r
    kg = data.get("knowledge_graph") or {}
    site = kg.get("website")
    if not site:
        candidates = [res for res in data.get("organic_results", [])[:10]
                      if not any(bad in _domain(res.get("link", "")) for bad in NOT_OFFICIAL)]
        token = _tokens(company)[0]
        # Strongest signal: the company's own name is in the domain (razorpay.com for "Razorpay").
        site = next((c["link"] for c in candidates if token in _root(_domain(c.get("link", "")))), None)
        if not site:
            site = next((c["link"] for c in candidates
                         if _mentions(company, c.get("title", "") + " " + _domain(c.get("link", "")))), None)
    if site:
        root = _root(_domain(site))
        r.data["official_domain"] = root
        r.signal, r.delta = "green", -10
        r.summary = f"Found an official website: {root}"
        r.evidence.append(_ev(kg.get("title") or company, site, kg.get("description", ""), "Website"))
        if kg:
            r.delta -= 4
            r.summary += " (Google also shows a knowledge panel)"
    else:
        r.signal, r.delta = "red", 12
        r.summary = "Couldn't find any website that belongs to this company"
    return r


def check_complaints(company: str) -> CheckResult:
    r = CheckResult("complaints", "Scam reports online", "Google Search")
    q = f'"{company}" (scam OR fraud OR fake OR cheated) internship'
    data = _run(r, {"engine": "google", "q": q, "gl": "in", "hl": "en"})
    if data is None:
        return r
    hits = []
    for res in data.get("organic_results", []):
        blob = f"{res.get('title', '')} {res.get('snippet', '')}"
        if SCAM_WORDS.search(blob) and _mentions(company, blob):
            hits.append(_ev(res.get("title", ""), res.get("link", ""), res.get("snippet", ""), _domain(res.get("link", ""))))
    r.evidence = hits[:4]
    if len(hits) >= 3:
        r.signal, r.delta = "red", 25
        r.summary = f"{len(hits)} pages link this company to scam / fraud complaints"
    elif hits:
        r.signal, r.delta = "amber", 6 * len(hits)
        r.summary = f"{len(hits)} page(s) mention this company together with scam / fraud"
    else:
        r.signal, r.delta = "green", -5
        r.summary = "No scam or fraud complaints found"
    return r


def check_maps(company: str) -> CheckResult:
    r = CheckResult("maps", "Physical office", "Google Maps")
    data = _run(r, {"engine": "google_maps", "q": company, "type": "search", "hl": "en"})
    if data is None:
        return r
    places = data.get("local_results") or ([data["place_results"]] if data.get("place_results") else [])
    place = next((p for p in places if _mentions(company, p.get("title", ""))), None)
    if not place:
        r.signal, r.delta = "amber", 8
        r.summary = "No office for this company on Google Maps"
        return r
    rating, reviews = place.get("rating"), place.get("reviews") or 0
    link = place.get("website") or f"https://www.google.com/maps/search/{company.replace(' ', '+')}"
    r.evidence.append(_ev(place.get("title", company), link, place.get("address", ""), "Google Maps"))
    if rating and reviews >= 5 and rating < 3:
        r.signal, r.delta = "amber", 6
        r.summary = f"Office listed, but rated {rating}★ from {reviews} reviews"
    else:
        r.signal, r.delta = "green", -8
        extra = f", {rating}★ from {reviews} reviews" if rating else ""
        r.summary = f"Office found: {place.get('address', 'address listed')}{extra}"
    return r


def check_news(company: str) -> CheckResult:
    r = CheckResult("news", "News coverage", "Google News")
    data = _run(r, {"engine": "google_news", "q": f'"{company}"', "gl": "in", "hl": "en"})
    if data is None:
        return r
    items = []
    for n in data.get("news_results", []):
        items.extend(n.get("stories", []) if "stories" in n else [n])
    items = [n for n in items if _mentions(company, n.get("title", "") + " " + (n.get("snippet") or ""))]
    # "X launches fraud detection" is not "X is a fraud": skip headlines about fighting fraud.
    bad = [n for n in items if SCAM_WORDS.search(n.get("title", "")) and not POSITIVE_CONTEXT.search(n.get("title", ""))]
    pick = (bad or items)[:3]
    r.evidence = [_ev(n.get("title", ""), n.get("link", ""), n.get("date", ""), (n.get("source") or {}).get("name", "")) for n in pick]
    if bad and len(items) >= 6 and len(bad) * 3 < len(items):
        # A well-covered company with a few fraud-related headlines is normal (e.g. payment firms).
        r.signal, r.delta = "amber", 3
        r.summary = f"{len(items)} news stories; {len(bad)} mention fraud, worth reading"
    elif bad:
        r.signal, r.delta = "red", 15
        r.summary = f"News stories link this company to fraud ({len(bad)})"
    elif len(items) >= 2:
        r.signal, r.delta = "green", -8
        r.summary = f"{len(items)} news stories about this company"
    elif items:
        r.signal, r.delta = "neutral", -2
        r.summary = "One news story mentions this company"
    else:
        r.signal, r.delta = "amber", 4
        r.summary = "No news coverage at all"
    return r


def check_jobs(company: str) -> CheckResult:
    r = CheckResult("jobs", "Real job listings", "Google Jobs")
    data = _run(r, {"engine": "google_jobs", "q": f"{company} jobs", "location": "India", "hl": "en"})
    if data is None:
        return r
    jobs = [j for j in data.get("jobs_results", []) if _mentions(company, j.get("company_name", ""))]
    for j in jobs[:3]:
        link = (j.get("apply_options") or [{}])[0].get("link") or j.get("share_link", "")
        r.evidence.append(_ev(j.get("title", ""), link, j.get("location", ""), j.get("via", "")))
    if jobs:
        r.signal, r.delta = "green", -8
        r.summary = f"{len(jobs)} real job listing(s) posted by this company"
    else:
        r.signal, r.delta = "amber", 5
        r.summary = "No job listings from this company on Google Jobs"
    return r


def check_linkedin(company: str) -> CheckResult:
    r = CheckResult("linkedin", "LinkedIn presence", "Google Search")
    data = _run(r, {"engine": "google", "q": f'"{company}" linkedin company page', "gl": "in", "hl": "en"})
    if data is None:
        return r
    page = next((x for x in data.get("organic_results", [])
                 if "linkedin.com/company" in x.get("link", "") and _mentions(company, x.get("title", ""))), None)
    if page:
        r.signal, r.delta = "green", -8
        r.summary = "Company has a LinkedIn page"
        r.evidence.append(_ev(page.get("title", ""), page.get("link", ""), page.get("snippet", ""), "LinkedIn"))
    else:
        r.signal, r.delta = "amber", 8
        r.summary = "No LinkedIn company page found"
    return r


def check_registry(company: str) -> CheckResult:
    r = CheckResult("registry", "Company registration (MCA)", "Google Search")
    data = _run(r, {"engine": "google", "q": f'"{company}" private limited CIN zaubacorp tofler', "gl": "in", "hl": "en"})
    if data is None:
        return r
    # A registry page (Zauba, Tofler, LEI…) titles the record with the legal name, e.g.
    # "RAZORPAY PAYMENTS PRIVATE LIMITED".
    legal = re.compile(r"\b(private\s+limited|pvt\.?\s*ltd|limited|llp)\b", re.I)
    rec = next((x for x in data.get("organic_results", [])
                if _mentions(company, x.get("title", ""))
                and (any(s in _domain(x.get("link", "")) for s in REGISTRY_SITES)
                     or (legal.search(x.get("title", "")) and x.get("title", "").isupper()))), None)
    if rec:
        r.signal, r.delta = "green", -8
        r.summary = f"Registered company record found: {rec.get('title', '')[:80]}"
        r.evidence.append(_ev(rec.get("title", ""), rec.get("link", ""), rec.get("snippet", ""), _domain(rec.get("link", ""))))
    else:
        r.signal, r.delta = "amber", 5
        r.summary = "No registered company record found in MCA mirrors (Zauba / Tofler)"
    return r


def check_contact(email: str | None, phones: list[str]) -> CheckResult:
    """Has this exact email address or phone number shown up in scam reports?"""
    r = CheckResult("contact", "Recruiter's email / phone history", "Google Search")
    targets = ([email] if email else []) + [f"+91 {p[:5]} {p[5:]}" if len(p) == 10 else p for p in phones[:1]]
    targets = [t for t in targets if "X" not in t.upper().replace("+91", "")]  # skip masked numbers
    if not targets:
        r.summary = "No email or phone number to look up"
        return r
    hits, seen = [], 0
    for t in targets:
        bare = t.replace("+91 ", "").replace(" ", "")
        data = _run(r, {"engine": "google", "q": f'"{bare}"', "gl": "in", "hl": "en"})
        if data is None:
            return r
        for res in data.get("organic_results", []):
            blob = f"{res.get('title', '')} {res.get('snippet', '')}"
            if bare.lower() not in blob.lower().replace(" ", ""):
                continue
            seen += 1
            if SCAM_WORDS.search(blob):
                hits.append(_ev(res.get("title", ""), res.get("link", ""), res.get("snippet", ""), _domain(res.get("link", ""))))
    r.evidence = hits[:3]
    shown = " / ".join(targets)
    if hits:
        r.signal, r.delta = "red", 20
        r.summary = f"{shown} already appears in {len(hits)} scam report(s)"
    elif seen:
        r.signal, r.summary = "neutral", f"{shown} appears online, but not in scam reports"
    else:
        r.signal, r.summary = "neutral", f"No public reports about {shown}"
    return r


def _has_mx(domain: str) -> bool | None:
    try:
        resp = requests.get("https://dns.google/resolve", params={"name": domain, "type": "MX"}, timeout=10)
        return bool(resp.json().get("Answer"))
    except (requests.RequestException, ValueError):
        return None


def check_email(email_domain: str | None, official_domain: str | None) -> CheckResult:
    r = CheckResult("email", "Recruiter email", "DNS + website match")
    if not email_domain:
        r.summary = "No email address in the message"
        return r
    if email_domain in FREE_MAIL_DOMAINS:
        r.signal, r.delta = "red", 15
        r.summary = f"Recruiter writes from a free {email_domain} address, not a company domain"
        return r
    if official_domain and (email_domain == official_domain or email_domain.endswith("." + official_domain)
                            or official_domain.endswith("." + email_domain)):
        r.signal, r.delta = "green", -10
        r.summary = f"Email domain {email_domain} matches the company website"
        return r
    mx = _has_mx(email_domain)
    if mx is False:
        r.signal, r.delta = "red", 15
        r.summary = f"{email_domain} can't even receive email (no MX record)"
    elif official_domain:
        r.signal, r.delta = "amber", 8
        r.summary = f"Email domain {email_domain} doesn't match the company website ({official_domain})"
    else:
        r.signal, r.delta = "neutral", 0
        r.summary = f"Email from {email_domain}, but there's no official website to compare with"
    return r


WEB_CHECKS = [check_complaints, check_maps, check_news, check_jobs, check_linkedin, check_registry]
STEP_TITLES = [
    ("message", "Red flags in the message", "Text analysis"),
    ("website", "Official website", "Google Search"),
    ("complaints", "Scam reports online", "Google Search"),
    ("maps", "Physical office", "Google Maps"),
    ("news", "News coverage", "Google News"),
    ("jobs", "Real job listings", "Google Jobs"),
    ("linkedin", "LinkedIn presence", "Google Search"),
    ("registry", "Company registration (MCA)", "Google Search"),
    ("email", "Recruiter email", "DNS + website match"),
    ("contact", "Recruiter's email / phone history", "Google Search"),
]
