import os

import pytest

os.environ["DATABASE_URL"] = "sqlite://"

from prospect_intel import db  # noqa: E402
from prospect_intel.db import NdpcRecord  # noqa: E402
from prospect_intel.matcher import match  # noqa: E402
from prospect_intel.scoring import score  # noqa: E402
from prospect_intel.signals import gap_signals  # noqa: E402


def rec(name, rc=None, domain=None):
    return NdpcRecord(list_name="dcmi", name=name, rc_number=rc, domain=domain, source_url="test")


def test_no_register_means_manual_review_not_unmatched():
    assert match("Any Bank", None, None, []).status == "Manual review"


def test_rc_and_domain_verify():
    recs = [rec("Totally Different Name", rc="1234567"), rec("Other", domain="acme.example")]
    assert match("Acme MFB", None, "RC 1234567", recs).basis == "RC number"
    assert match("Acme", "acme.example", None, recs).status == "Verified"


def test_name_bands():
    recs = [rec("Zuma Micro Finance Bank Limited"), rec("Wellguard Health Services Ltd")]
    assert match("Zuma MFB", None, None, recs).status == "Verified"
    assert match("Wellguard", None, None, recs).status == "Manual review"
    assert match("Completely Unrelated Clinic", None, None, recs).status == "Unmatched"


def test_ambiguous_names_go_to_review():
    recs = [rec("Unity Hospital Lagos"), rec("Unity Hospitals Lagos")]
    assert match("Unity Hospital Lagos", None, None, recs).status == "Manual review"


def test_no_gaps_when_not_crawled():
    assert gap_signals(set(), 0) == []
    total, b = score("health", [], [], "unknown", "Unmatched", ["x"], False, False, False, 0)
    assert b["gap_signals"] == 0


def test_demo_end_to_end(tmp_path):
    eng = db.engine(f"sqlite:///{tmp_path/'t.db'}")
    db.init_db(eng)
    from prospect_intel.demo import load_demo
    from prospect_intel.export import leads_frame

    with db.session(eng) as s:
        assert load_demo(s) == 8
        df = leads_frame(s)
    assert set(df.ndpc_status) <= {"Verified", "Unmatched", "Manual review"}
    robots = df[df.name == "Brightseed Fertility Centre"].iloc[0]
    assert robots.gap_signals == "" or robots.gap_signals != robots.gap_signals  # no gaps claimed when robots blocks
    assert df.score.between(0, 100).all()
    # No wording that asserts non-compliance
    text = " ".join(df.next_step.tolist() + df.summary.tolist()).lower()
    for banned in ("non-compliant", "noncompliant", "in breach", "violat", "unregistered"):
        assert banned not in text
