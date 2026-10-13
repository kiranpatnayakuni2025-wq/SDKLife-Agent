"""Runs a whole search: discover -> research each college -> score -> save."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from . import config, demo, discover, research, scoring, store


def _one(inst: dict, params: dict, use_demo: bool) -> dict:
    record = {"name": inst.get("name", ""), "city": inst.get("city", ""), "state": inst.get("state", ""),
              "type": inst.get("type", ""), "website": inst.get("website", "")}
    try:
        data, urls = (demo.research if use_demo else research.research)(inst, params)
        if data.get("hostel_students") is None and inst.get("hostel_students") is not None:
            data["hostel_students"] = inst["hostel_students"]  # fall back to discovery estimate
            data["hostel_students_basis"] = (inst.get("hostel_students_basis") or "") + " (from discovery)"
        record["research"] = data
        record["verified_urls"] = sorted(urls)
        record["score"] = scoring.score_institution(data, urls)
    except Exception as exc:  # one failing college must not stop the run
        record["error"] = str(exc)
        record["score"] = {"priority": "Thin evidence", "adjusted": 0, "raw": 0, "multiplier": 0,
                           "confidence": "Low", "breakdown": [], "signals": [],
                           "flags": [f"Research failed: {exc}"], "best_tier": None}
        record["research"] = {}
    return record


def run_search(params: dict, use_demo: bool, on_progress=lambda done, total, msg: None) -> dict:
    now = datetime.now()
    region = params["states"] or params["cities"] or "India"
    run = {
        "id": now.strftime("%Y%m%d-%H%M%S"),
        "created": now.isoformat(timespec="seconds"),
        "demo": use_demo,
        "label": f"{now:%d %b %H:%M} - {region}" + (" (DEMO)" if use_demo else ""),
        "params": params,
        "institutions": [],
        "status": "running",
    }
    on_progress(0, 1, "Finding colleges that match your search...")
    found = (demo.discover if use_demo else discover.discover)(params)
    found = found[: int(params["max_colleges"])]
    total = len(found)
    if total == 0:
        raise RuntimeError("No matching colleges were found. Try wider cities or lower the hostel minimum.")
    on_progress(0, total, f"Found {total} colleges. Researching each one...")

    done = 0
    with ThreadPoolExecutor(max_workers=1 if use_demo else config.parallel()) as pool:
        futures = {pool.submit(_one, inst, params, use_demo): inst for inst in found}
        for fut in as_completed(futures):
            rec = fut.result()
            run["institutions"].append(rec)
            store.save_run(run)  # save as we go, so nothing is lost if the window is closed
            done += 1
            on_progress(done, total, f"Finished {rec['name']} ({done}/{total})")
    run["status"] = "done"
    store.save_run(run)
    return run


def ranked(run: dict):
    return sorted(run["institutions"],
                  key=lambda r: (scoring.PRIORITY_ORDER.get(r["score"]["priority"], 9), -r["score"]["adjusted"]))
