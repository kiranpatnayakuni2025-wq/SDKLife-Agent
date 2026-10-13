"""Scoring rules from the approved 'Ideal Customer & Scoring Sheet' (Stage 1).

All scoring happens here, in plain code, so every point can be traced.
The AI only reports facts (signals, sizes, levels with reasons); it never sets the score.
Change the numbers below to change how colleges are ranked.
"""
import re
from datetime import date
from urllib.parse import urlparse

# ---- The approved weights (total 100) -------------------------------------
WEIGHTS = {
    "buying_intent": 25,
    "problem_fit": 20,
    "signal_strength": 15,
    "recency": 15,
    "campus_scale": 15,
    "digital_readiness": 10,
}
LABELS = {
    "buying_intent": "Buying intent",
    "problem_fit": "Problem fit",
    "signal_strength": "Signal strength",
    "recency": "Recency",
    "campus_scale": "Campus scale",
    "digital_readiness": "Digital readiness",
}
# Evidence confidence multiplies the total.
CONFIDENCE_MULTIPLIER = {"High": 1.0, "Medium": 0.85, "Low": 0.6}

# Priority cut-offs (adjusted score).
HIGH_MIN = 70
MEDIUM_MIN = 45

# Recency: months since the newest sourced signal.
RECENT_MONTHS = 6
OLD_MONTHS = 18

# Campus scale: hostel students.
LARGE_HOSTEL = 2000
MIN_HOSTEL = 500

TIER_RANK = {"direct": 3, "strong_need": 2, "indirect": 1}
TIER_LABEL = {"direct": "Direct", "strong_need": "Strong need", "indirect": "Indirect"}
TIER_STRENGTH = {"direct": "Strong", "strong_need": "Medium", "indirect": "Weak"}
PRIORITY_ORDER = {"High": 0, "Medium": 1, "Low": 2, "Thin evidence": 3}


def norm_url(url: str) -> str:
    """Same college page written slightly differently should compare equal."""
    try:
        p = urlparse(url.strip())
        host = p.netloc.lower().removeprefix("www.")
        path = p.path.rstrip("/")
        return f"{host}{path}" + (f"?{p.query}" if p.query else "")
    except Exception:
        return url.strip().lower()


def parse_date(text):
    """Accepts YYYY-MM-DD, YYYY-MM or YYYY. Returns a date or None."""
    if not text:
        return None
    m = re.match(r"^\s*(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?", str(text))
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2) or 6), int(m.group(3) or 15))
    except ValueError:
        return None


def _level(value) -> int:
    try:
        return max(0, min(2, int(value)))
    except (TypeError, ValueError):
        return 0


def _tier(value) -> str:
    v = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    return v if v in TIER_RANK else "indirect"


def mark_verified(signals, verified_urls):
    """A signal only counts if its link really appeared in the search results."""
    seen = {norm_url(u) for u in verified_urls}
    out = []
    for s in signals or []:
        s = dict(s)
        s["tier"] = _tier(s.get("tier"))
        url = (s.get("source_url") or "").strip()
        s["verified"] = bool(url) and norm_url(url) in seen
        out.append(s)
    return out


def score_institution(research: dict, verified_urls, today: date = None) -> dict:
    today = today or date.today()
    signals = mark_verified(research.get("signals"), verified_urls)
    ver = [s for s in signals if s["verified"]]
    best_rank = max((TIER_RANK[s["tier"]] for s in ver), default=0)
    has_strong = best_rank >= TIER_RANK["strong_need"]
    has_direct = best_rank >= TIER_RANK["direct"]

    parts = []  # (key, points, note)

    # Buying intent: cannot claim more than the sourced signals support.
    bi = _level(research.get("buying_intent"))
    if not has_strong:
        bi = 0
    elif not has_direct:
        bi = min(bi, 1)
    parts.append(("buying_intent", WEIGHTS["buying_intent"] * bi / 2,
                  research.get("buying_intent_reason") or "No active procurement found."))

    pf = _level(research.get("problem_fit"))
    parts.append(("problem_fit", WEIGHTS["problem_fit"] * pf / 2,
                  research.get("problem_fit_reason") or "No evidence on how student movement is handled."))

    if has_direct:
        ss, ss_note = 1.0, "Direct signal found."
    elif best_rank == TIER_RANK["strong_need"]:
        ss, ss_note = 0.5, "Strong-need signal found, no direct signal."
    else:
        ss, ss_note = 0.0, "Indirect signals only." if ver else "No sourced signals."
    parts.append(("signal_strength", WEIGHTS["signal_strength"] * ss, ss_note))

    dates = [parse_date(s.get("date")) for s in ver]
    dates = [d for d in dates if d]
    if dates:
        newest = max(dates)
        months = (today - newest).days / 30.44
        if months <= RECENT_MONTHS:
            rc, rc_note = 1.0, f"Newest sourced signal is from {newest:%b %Y} (within {RECENT_MONTHS} months)."
        elif months <= OLD_MONTHS:
            rc, rc_note = 0.5, f"Newest sourced signal is from {newest:%b %Y} ({RECENT_MONTHS}-{OLD_MONTHS} months old)."
        else:
            rc, rc_note = 0.0, f"Newest sourced signal is from {newest:%b %Y} (older than {OLD_MONTHS} months)."
    else:
        rc, rc_note = 0.0, "No dated, sourced signal."
    parts.append(("recency", WEIGHTS["recency"] * rc, rc_note))

    hostel = research.get("hostel_students")
    try:
        hostel = int(hostel) if hostel is not None else None
    except (TypeError, ValueError):
        hostel = None
    if hostel is None:
        cs, cs_note = 0.0, "Hostel population not found."
    elif hostel >= LARGE_HOSTEL:
        cs, cs_note = 1.0, f"About {hostel:,} hostel students."
    elif hostel >= MIN_HOSTEL:
        cs, cs_note = 0.5, f"About {hostel:,} hostel students."
    else:
        cs, cs_note = 0.0, f"About {hostel:,} hostel students (under {MIN_HOSTEL})."
    parts.append(("campus_scale", WEIGHTS["campus_scale"] * cs, cs_note))

    dr = _level(research.get("digital_readiness"))
    parts.append(("digital_readiness", WEIGHTS["digital_readiness"] * dr / 2,
                  research.get("digital_readiness_reason") or "No evidence of digital tools."))

    raw = sum(p for _, p, _ in parts)

    # Evidence confidence: the AI's view, held down when sources are weak.
    conf = str(research.get("evidence_confidence") or "Low").strip().capitalize()
    if conf not in CONFIDENCE_MULTIPLIER:
        conf = "Low"
    if not ver:
        conf = "Low"
    elif conf == "High" and not any(s.get("source_type") in ("official", "portal") for s in ver):
        conf = "Medium"
    mult = CONFIDENCE_MULTIPLIER[conf]
    adjusted = round(raw * mult, 1)

    if not ver:
        priority = "Thin evidence"
    elif adjusted >= HIGH_MIN and has_strong:
        priority = "High"
    elif adjusted >= MEDIUM_MIN:
        priority = "Medium"
    else:
        priority = "Low"

    flags = []
    if hostel is None:
        flags.append("Hostel size unknown - check by hand.")
    elif hostel < MIN_HOSTEL:
        flags.append(f"Below the {MIN_HOSTEL} hostel-student minimum.")
    unverified = [s for s in signals if not s["verified"]]
    if unverified:
        flags.append(f"{len(unverified)} claimed signal(s) had no verifiable source and were not counted.")

    breakdown = [
        {"dimension": LABELS[k], "points": round(p, 1), "max": WEIGHTS[k], "note": n}
        for k, p, n in parts
    ]
    return {
        "raw": round(raw, 1),
        "multiplier": mult,
        "confidence": conf,
        "adjusted": adjusted,
        "priority": priority,
        "breakdown": breakdown,
        "signals": signals,
        "best_tier": next((t for t, r in TIER_RANK.items() if r == best_rank), None),
        "flags": flags,
    }
