# 🕵️ OfferCheck: is that internship offer real?

**Paste an internship offer. OfferCheck investigates the company live across Google Search, Maps, News, Jobs and company registries using [SerpApi](https://serpapi.com), and shows you a risk score with the evidence behind every point.**

Built for the SerpApi India Hackathon 2026 · Track: **Knowledge & Public Interest**

---

## The problem

Every week, Indian students get messages like this:

> *"Congratulations! You are selected for the Web Development Internship. No interview required. Pay the refundable registration fee of Rs 2,999 within 24 hours. Send your Aadhaar on WhatsApp."*

Fake internship and job offers are one of the most common frauds aimed at students. The usual advice is "verify the company", but that means doing a dozen Google searches by hand: does it have a website, an office, real job listings, news coverage, a LinkedIn page, a registration record, any scam complaints? Most students don't, and some lose money or share their documents.

Existing "fake job detectors" only guess from the message text. **OfferCheck goes out and checks the real world, and shows its sources.**

## What it does

1. Reads the message and pulls out the **company name** and **recruiter email**.
2. Flags scam wording in the message: asking for money, Aadhaar/bank details, "no interview", urgency, WhatsApp-only contact, unrealistic per-day pay.
3. Runs **9 live checks** in parallel, streaming each result to the screen as it finishes.
4. Combines everything into a **0–100 risk score** with the reasons, evidence links and what to do next.
5. Catches **impersonation**: when a real company's name (say, Infosys) is used from a Gmail address with a fee request, it raises an impersonation alert instead of trusting the famous name.
6. Understands **Hinglish** WhatsApp scams ("fees jama karo", "aaj hi").
7. One click turns the result into a **WhatsApp warning** you can forward to your college group.

| Check | Data source (SerpApi engine) | What it tells you |
|---|---|---|
| Official website | `google` (organic results + knowledge graph) | Does the company have its own website and a Google knowledge panel? |
| Scam reports | `google` | Are there pages linking the company to scam / fraud complaints? |
| Physical office | `google_maps` | Is there a real office? What's its rating? |
| News coverage | `google_news` | Is the company in the news, and is that news about fraud? |
| Real job listings | `google_jobs` | Is the company actually hiring through normal channels? |
| LinkedIn presence | `google` (`site:linkedin.com/company`) | Does it have a LinkedIn company page? |
| Company registration | `google` (MCA registry mirrors: Zauba, Tofler) | Is it a registered Indian company (CIN record)? |
| Recruiter email | DNS (Google DoH) + the website found above | Free Gmail "HR"? Domain that can't receive mail? Domain that doesn't match the company? |
| Recruiter's email / phone history | `google` (exact email or phone number) | Has this exact contact already been reported in scam posts? |

**Without live search data the app cannot work.** Every web signal comes from a SerpApi engine.

### Scoring

The score starts at 25. Each check adds risk (red / amber) or removes it (green). Message red flags add up to 45 points. **Any request for money puts the score at 70 or above**, because genuine companies never charge interns. An impersonation alert puts it at 80 or above. 65 and above means "High risk", 35 to 64 means "Be careful", and below 35 means "Looks legitimate". Every point is shown with its evidence, so the user can judge for themselves.

## Run it locally

Requirements: Python 3.10+

```bash
git clone https://github.com/MG782469/offercheck.git
cd offercheck
pip install -r requirements.txt
cp .env.example .env        # then put your SerpApi key in .env
python app.py
```

Open **http://localhost:8000**, paste an offer, or click **"Try a scam message"** / **"Try a real offer"**.

Get a free SerpApi key (250 searches/month) at [serpapi.com](https://serpapi.com/users/sign_up).

### Cache

Every SerpApi response is cached in `cache/`, keyed by the query (never by your API key). Re-checking a company costs no credits. The repository ships with the cache for the two sample messages, so the demo works even without a key.

### Tests

```bash
python -m pytest -q
```

## API

`POST /api/investigate` with `{"text": "...", "company": null, "email": null}` streams newline-delimited JSON events: one `start`, one `step` per check (signal, score delta, summary, evidence links), and a final `verdict`.

## Project structure

```
app.py          FastAPI server and streaming endpoint
investigate.py  runs the checks in parallel and builds the verdict
checks.py       one function per live check (SerpApi engines + DNS)
analyzer.py     company/email extraction and red-flag rules for the message
serp.py         SerpApi client with on-disk cache
static/         single-page UI (no build step)
tests/          unit tests
```

## Limitations

- These are risk signals from public web data, not a legal verdict. A brand-new genuine startup can look thin online; a scammer can borrow a real company's name. That's why every signal comes with evidence to check.
- Company name detection uses patterns; if it guesses wrong, type the name in the Company box.
- Only the company name and email domain are sent to SerpApi. The message itself never leaves your machine.

## Report fraud

India: [cybercrime.gov.in](https://cybercrime.gov.in) or call **1930**.

## AI disclosure

Built with help from Claude (Anthropic), which helped shape the idea and write and review the code. I tested it and recorded the demo.
