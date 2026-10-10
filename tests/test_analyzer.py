import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import analyzer  # noqa: E402
import checks  # noqa: E402
import investigate  # noqa: E402

SCAM = """Dear Candidate, you are selected at Zentrova Skillnet Solutions Pvt Ltd. No interview required.
Pay the registration fee of Rs 2,999 within 24 hours and send your Aadhaar on WhatsApp.
Contact zentrova.hr2026@gmail.com"""

REAL = """Hi Manas, thanks for interviewing with us. We're happy to offer you an intern role at Razorpay.
Talent Team, careers@razorpay.com"""


def ids(text):
    return {f.id for f in analyzer.text_flags(text)}


def test_scam_message_flags():
    assert {"asks_payment", "asks_documents", "no_interview", "urgency", "off_platform", "generic_greeting"} <= ids(SCAM)


def test_real_message_has_no_flags():
    assert ids(REAL) == set()


def test_extracts_company_and_email():
    scam = analyzer.extract(SCAM)
    assert scam.company == "Zentrova Skillnet Solutions Pvt Ltd"
    assert scam.email_domain == "gmail.com"
    real = analyzer.extract(REAL)
    assert real.company == "Razorpay"
    assert real.email_domain == "razorpay.com"


def test_explicit_company_wins():
    assert analyzer.extract(SCAM, company="Acme").company == "Acme"


def test_free_mail_is_red():
    r = checks.check_email("gmail.com", "zentrova.com")
    assert r.signal == "red" and r.delta > 0


def test_matching_domain_is_green():
    r = checks.check_email("razorpay.com", "razorpay.com")
    assert r.signal == "green" and r.delta < 0


def test_payment_request_forces_high_risk():
    flags = analyzer.text_flags(SCAM)
    goods = [checks.CheckResult(str(i), "x", "y", signal="green", delta=-10) for i in range(8)]
    assert investigate.verdict(goods, flags)["score"] >= investigate.PAYMENT_FLOOR
