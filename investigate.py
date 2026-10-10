"""Runs every check for one offer and streams results as they finish."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterator

import analyzer
import checks

BASE_RISK = 25
PAYMENT_FLOOR = 70  # real companies never charge interns; any fee request means high risk


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


def verdict(results: list[checks.CheckResult], flags: list[analyzer.Flag]) -> dict:
    score = BASE_RISK + sum(r.delta for r in results)
    asks_money = any(f.id == "asks_payment" for f in flags)
    if asks_money:
        score = max(score, PAYMENT_FLOOR)
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
    if level != "low":
        advice.append("Contact the company only through details on its official website.")
        advice.append("Don't share Aadhaar, PAN or bank details. Report fraud at cybercrime.gov.in or call 1930.")
    errors = sum(1 for r in results if r.signal == "error")
    return {
        "type": "verdict",
        "score": score,
        "level": level,
        "headline": headline,
        "red": [r.summary for r in reasons[:4]],
        "green": [r.summary for r in goods[:4]],
        "advice": advice,
        "incomplete": errors,
    }


def investigate(text: str, company: str | None = None, email: str | None = None) -> Iterator[dict]:
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
        yield verdict(results, flags)
        return

    website = checks.check_website(info.company)
    results.append(website)
    yield {"type": "step", **website.to_dict()}

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(fn, info.company) for fn in checks.WEB_CHECKS]
        futures.append(pool.submit(checks.check_email, info.email_domain, website.data.get("official_domain")))
        for fut in as_completed(futures):
            res = fut.result()
            results.append(res)
            yield {"type": "step", **res.to_dict()}

    yield verdict(results, flags)
