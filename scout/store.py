"""Saves runs and your shortlist decisions to the data folder."""
import json
from pathlib import Path

from . import config

DECISIONS_FILE = config.DATA_DIR / "decisions.json"
DECISION_OPTIONS = ["Not reviewed", "Shortlisted", "Review Later", "Not Relevant"]


def _write(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def save_run(run: dict):
    _write(config.RUNS_DIR / f"{run['id']}.json", run)


def load_run(run_id: str):
    p = config.RUNS_DIR / f"{run_id}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def list_runs():
    runs = []
    for p in sorted(config.RUNS_DIR.glob("*.json"), reverse=True):
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
            runs.append({"id": r["id"], "created": r.get("created", ""), "demo": r.get("demo", False),
                         "label": r.get("label", r["id"]), "count": len(r.get("institutions", []))})
        except Exception:
            continue
    return runs


def inst_key(inst: dict) -> str:
    return f"{inst.get('name', '').strip().lower()}|{inst.get('city', '').strip().lower()}"


def load_decisions() -> dict:
    if DECISIONS_FILE.exists():
        try:
            return json.loads(DECISIONS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def set_decision(inst: dict, decision: str):
    d = load_decisions()
    d[inst_key(inst)] = decision
    _write(DECISIONS_FILE, d)
