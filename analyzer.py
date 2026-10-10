"""Reads the offer message itself: pulls out the company / email and spots scam wording."""
import re
from dataclasses import dataclass, field

FREE_MAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.in", "yahoo.co.in", "outlook.com",
    "hotmail.com", "live.com", "rediffmail.com", "protonmail.com", "proton.me", "icloud.com",
    "aol.com", "zoho.com", "yandex.com", "mail.com", "gmx.com",
}

COMPANY_SUFFIX = (
    r"(?:Pvt\.?\s*Ltd\.?|Private\s+Limited|Technologies|Technology|Solutions|Labs|Infotech|"
    r"Infosystems|Systems|Software|Softwares|Services|Consultancy|Consulting|Ventures|Global|"
    r"Inc\.?|LLP|Ltd\.?|Limited|Corporation|Corp\.?)"
)
# Names never span lines or sentences, so words are joined by spaces/tabs only.
_COMPANY_WITH_SUFFIX = re.compile(
    r"\b((?:[A-Z][A-Za-z0-9&\-]*[ \t]+){0,4}[A-Z][A-Za-z0-9&\-]*[ \t]+" + COMPANY_SUFFIX + r")"
)
_COMPANY_AFTER_WORD = re.compile(
    r"\b(?:at|from|with|join|joining|by)[ \t]+([A-Z][A-Za-z0-9&\-]+(?:[ \t]+[A-Z][A-Za-z0-9&\-]+){0,3})"
)
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_STOP_WORDS = {"The", "Our", "We", "You", "Your", "Dear", "Hi", "Hello", "Congratulations", "Team", "HR"}


@dataclass
class Flag:
    id: str
    label: str
    weight: int
    quote: str


@dataclass
class Extracted:
    company: str | None
    emails: list[str] = field(default_factory=list)

    @property
    def email(self) -> str | None:
        return self.emails[0] if self.emails else None

    @property
    def email_domain(self) -> str | None:
        return self.email.split("@", 1)[1].lower() if self.email else None


# (id, label, weight, pattern). Weights are added to the risk score.
_RULES = [
    ("asks_payment", "Asks you to pay money (fee / deposit / charges)", 35,
     r"(registration|training|security|certificate|certification|joining|onboarding|processing|"
     r"enrol?ment|kit|refundable)\s*(fee|fees|charges?|deposit|amount)"
     r"|(pay|deposit|transfer)\s+(an?\s+amount\s+of\s+)?(rs\.?|inr|₹)\s*\d"
     r"|(₹|rs\.?|inr)\s?\d[\d,]*\s*(/-)?\s*(only\s*)?(as|for|towards)\s+(the\s+)?\w*\s*(fee|charges|deposit)"),
    ("asks_documents", "Asks for sensitive documents or bank details up front", 15,
     r"\b(aadhaa?r|pan\s*card|bank\s*(account|details|statement)|ifsc|upi\s*pin|otp|cvv|passbook)\b"),
    ("no_interview", "Offer without any interview", 12,
     r"(no\s+interview|without\s+(any\s+)?interview|direct\s+(selection|joining|hiring)|"
     r"selected\s+without|no\s+test\s+required)"),
    ("urgency", "Pressure to act immediately", 8,
     r"(within\s+\d+\s*(hours?|hrs?|days?)|today\s+itself|limited\s+(seats|slots|positions)|"
     r"last\s+date\s+(is\s+)?today|before\s+(midnight|tonight)|act\s+fast|hurry)"),
    ("off_platform", "Moves the conversation to WhatsApp / Telegram", 8,
     r"\b(whats\s?app|telegram)\b"),
    ("unrealistic_pay", "Unrealistic pay promise (per day / per hour)", 10,
     r"(₹|rs\.?|inr)\s?\d[\d,]*\s*(/-)?\s*(per|/|a)\s*(day|hour|hr)\b"),
    ("generic_greeting", "Generic greeting instead of your name", 4,
     r"\bdear\s+(candidate|applicant|student|aspirant|sir\s*/\s*madam)\b"),
]
_COMPILED = [(i, label, w, re.compile(p, re.IGNORECASE)) for i, label, w, p in _RULES]


def _clean_company(name: str) -> str:
    words = [w for w in name.strip(" .,-").split() if w not in _STOP_WORDS]
    return " ".join(words).strip(" .,-")


def extract(text: str, company: str | None = None, email: str | None = None) -> Extracted:
    emails = [email.strip()] if email and email.strip() else []
    emails += [e for e in _EMAIL.findall(text) if e not in emails]

    name = (company or "").strip() or None
    if not name:
        match = _COMPANY_WITH_SUFFIX.search(text)
        if match:
            name = _clean_company(match.group(1))
    if not name:
        match = _COMPANY_AFTER_WORD.search(text)
        if match:
            name = _clean_company(match.group(1))
    if not name and emails:
        domain = emails[0].split("@", 1)[1].lower()
        if domain not in FREE_MAIL_DOMAINS:
            name = domain.split(".")[0].capitalize()
    return Extracted(company=name or None, emails=emails)


def text_flags(text: str) -> list[Flag]:
    flags = []
    for flag_id, label, weight, pattern in _COMPILED:
        match = pattern.search(text)
        if match:
            start, end = max(0, match.start() - 40), min(len(text), match.end() + 40)
            quote = " ".join(text[start:end].split())
            flags.append(Flag(flag_id, label, weight, quote))
    return flags
