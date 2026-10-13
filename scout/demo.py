"""Sample data so you can try the screens without an API key or any cost.
Every college here is INVENTED. Nothing in demo mode is real research.
"""
import time
from datetime import date, timedelta

_BASE = "https://example.com/demo"


def _ago(days):
    return (date.today() - timedelta(days=days)).isoformat()


_COLLEGES = [
    dict(name="DEMO Aravalli Institute of Technology", city="Jaipur", state="Rajasthan", type="Engineering college",
         website=f"{_BASE}/aravalli", hostel_students=3200,
         signals=[
             ("direct", "Tender notice for a biometric and digital gate-pass system for hostels.", 40, "official"),
             ("strong_need", "Smart-campus programme announced with ERP upgrade.", 120, "news"),
             ("indirect", "Hostel rules still require signing the gate register.", 200, "official"),
         ], bi=2, pf=2, dr=2, conf="High"),
    dict(name="DEMO Mewar School of Management", city="Udaipur", state="Rajasthan", type="B-school",
         website=f"{_BASE}/mewar", hostel_students=900,
         signals=[
             ("strong_need", "Hostel management software procurement mentioned in annual report.", 150, "official"),
             ("indirect", "Campus expansion adds two new hostel blocks.", 90, "news"),
         ], bi=1, pf=2, dr=1, conf="Medium"),
    dict(name="DEMO Thar Central University", city="Jodhpur", state="Rajasthan", type="Central university",
         website=f"{_BASE}/thar", hostel_students=2600,
         signals=[
             ("strong_need", "Biometric attendance rollout for students.", 700, "news"),
             ("indirect", "Large resident population across eight hostels.", 700, "official"),
         ], bi=0, pf=1, dr=1, conf="Medium"),
    dict(name="DEMO Hadoti Private University", city="Kota", state="Rajasthan", type="Private university",
         website=f"{_BASE}/hadoti", hostel_students=1500,
         signals=[("indirect", "Hostel brochure mentions 'register at gate'.", 400, "other")],
         bi=0, pf=2, dr=0, conf="Low"),
    dict(name="DEMO Ajmer College of Arts", city="Ajmer", state="Rajasthan", type="State college",
         website=f"{_BASE}/ajmer", hostel_students=250, signals=[], bi=0, pf=0, dr=0, conf="Low"),
]


def discover(params):
    time.sleep(0.4)
    keys = ("name", "city", "state", "type", "website", "hostel_students")
    out = []
    for c in _COLLEGES[: params["max_colleges"]]:
        item = {k: c[k] for k in keys}
        item["hostel_students_basis"] = "Demo estimate"
        out.append(item)
    return out


def research(inst, params):
    time.sleep(0.4)
    c = next(x for x in _COLLEGES if x["name"] == inst["name"])
    signals, urls = [], set()
    for i, (tier, text, days, stype) in enumerate(c["signals"]):
        url = f"{_BASE}/{c['name'].split()[1].lower()}/source-{i + 1}"
        urls.add(url.removeprefix("https://"))
        signals.append(dict(tier=tier, description=text, date=_ago(days), source_url=url,
                            source_title=f"Demo source {i + 1}", source_type=stype))
    if c["name"].endswith("Ajmer College of Arts"):
        signals.append(dict(tier="indirect", description="A claim with no real source (shows how unverified leads appear).",
                            date=_ago(30), source_url="https://example.com/never-searched", source_title="", source_type="other"))
    data = dict(
        institution=c["name"], hostel_students=c["hostel_students"], hostel_students_basis="Demo data",
        campus_summary=f"DEMO: {c['type']} in {c['city']} with about {c['hostel_students']} hostel students.",
        signals=signals, buying_intent=c["bi"], buying_intent_reason="Demo reasoning.",
        problem_fit=c["pf"], problem_fit_reason="Demo reasoning.",
        digital_readiness=c["dr"], digital_readiness_reason="Demo reasoning.",
        evidence_confidence=c["conf"],
        why_shortlisted="DEMO: sample text showing where the explanation for a salesperson will appear.",
        potential_fit="Digital outpass with QR gate logging and photo verification.",
        outreach_angle="DEMO: open with how the gate register slows students and wardens down.",
        gaps="DEMO: nothing real was researched.",
    )
    return data, urls
