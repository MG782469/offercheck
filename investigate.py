"""Runs every check for one offer and streams results as they finish."""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterator

import analyzer
import checks

BASE_RISK = 25
PAYMENT_FLOOR = 70  # real companies never charge interns; any fee request means high risk
PAYMENT_FLAGS = {"asks_payment", "asks_payment_hinglish"}


def _message_step(flags: list[analyzer.Flag]) -> checks.CheckResult:
    r = checks.CheckResult("message", "Red flags in the message", "Text analysis")
    r.evidence = [checks._ev(f.label, "", f'"…{f.quote}…"', "Message") for f in flags]
    if not flags:
        r.signal, r.delta, r.summary = "green", -5, "No scam wording found in the message"
        return r
    r.delta = min(sum(f.weight for f in flags), 45)
    r.signal = "red" if r.delta >= 15 else "amber"
    r.summary = f"{len(flags)} red flag(s): " + "; ".join(f.label.lower() for f in flags[:3])
    return r


def _impersonation(company: str | None, results: list[checks.CheckResult], asks_money: bool) -> str | None:
    """A real company's name used from an address that isn't theirs, usually with a fee request."""
    by_id = {r.id: r for r in results}
    website, email = by_id.get("website"), by_id.get("email")
    if not (company and website and email and website.signal == "green"):
        return None
    if email.signal in ("red", "amber") and (asks_money or email.signal == "red"):
        domain = website.data.get("official_domain", "their website")
        return f"Impersonation alert: {company} is real, but this message didn't come from {domain}."
    return None


def verdict(results: list[checks.CheckResult], flags: list[analyzer.Flag],
            company: str | None = None, elapsed: float = 0.0) -> dict:
    score = BASE_RISK + sum(r.delta for r in results)
    asks_money = any(f.id in PAYMENT_FLAGS for f in flags)
    impersonation = _impersonation(company, results, asks_money)
    if asks_money:
        score = max(score, PAYMENT_FLOOR)
    if impersonation:
        score = max(score, 80)
    score = max(0, min(100, score))
    if score >= 65:
        level, headline = "high", "High risk: this looks like a scam"
    elif score >= 35:
        level, headline = "medium", "Be careful: verify before you share anything"
    else:
        level, headline = "low", "Looks legitimate"
    reasons = sorted((r for r in results if r.delta > 0), key=lambda r: -r.delta)
    goods = sorted((r for r in results if r.delta < 0), key=lambda r: r.delta)
    advice = []
    if asks_money:
        advice.append("Never pay to get an internship. Genuine companies don't charge fees.")
    if impersonation:
        advice.append("Write to the company only through the contact details on its official website.")
    elif level != "low":
        advice.append("Contact the company only through details on its official website.")
    if level != "low":
        advice.append("Don't share Aadhaar, PAN or bank details. Report fraud at cybercrime.gov.in or call 1930.")
    return {
        "type": "verdict",
        "score": score,
        "level": level,
        "headline": headline,
        "impersonation": impersonation,
        "company": company,
        "red": [r.summary for r in reasons[:4]],
        "green": [r.summary for r in goods[:4]],
        "advice": advice,
        "incomplete": sum(1 for r in results if r.signal == "error"),
        "stats": {
            "sources": sum(1 for r in results if r.id != "message"),
            "results": sum(r.results for r in results),
            "seconds": round(elapsed, 1),
        },
    }


def investigate(text: str, company: str | None = None, email: str | None = None) -> Iterator[dict]:
    started = time.perf_counter()
    info = analyzer.extract(text, company, email)
    flags = analyzer.text_flags(text)
    yield {
        "type": "start",
        "company": info.company,
        "email": info.email,
        "steps": [{"id": i, "title": t, "engine": e} for i, t, e in checks.STEP_TITLES],
    }

    results = [_message_step(flags)]
    yield {"type": "step", **results[0].to_dict()}

    if not info.company:
        yield {"type": "error", "message": "Couldn't find a company name in the message. Type it in the Company box and try again."}
        yield verdict(results, flags, None, time.perf_counter() - started)
        return

    website = checks.check_website(info.company)
    results.append(website)
    yield {"type": "step", **website.to_dict()}

    with ThreadPoolExecutor(max_workers=7) as pool:
        futures = [pool.submit(fn, info.company) for fn in checks.WEB_CHECKS]
        futures.append(pool.submit(checks.check_email, info.email_domain, website.data.get("official_domain")))
        futures.append(pool.submit(checks.check_contact, info.email, info.phones))
        for fut in as_completed(futures):
            res = fut.result()
            results.append(res)
            yield {"type": "step", **res.to_dict()}

    yield verdict(results, flags, info.company, time.perf_counter() - started)
