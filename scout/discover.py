"""Step 1: find institutions that match the search."""
from datetime import date

from . import config, llm, prompts


def discover(params: dict):
    count = int(params["max_colleges"])
    body = prompts.DISCOVER_BODY.format(
        today=date.today().isoformat(),
        count=count + max(3, count // 3),  # a few extra: some drop out after research
        states=params["states"] or "India",
        cities=params["cities"] or "any major city",
        types=", ".join(params["types"]) or "any higher-education institution",
        min_hostel=params["min_hostel"],
        residential="required" if params.get("residential_only", True) else "preferred",
    )
    states = params["states"] or "India"
    city_list = [c.strip() for c in (params["cities"] or "").split(",") if c.strip()][:6]
    queries = [f"colleges universities in {c} {states} with hostels residential campus" for c in city_list]
    queries += [f"{t} {states} residential campus hostel" for t in (params["types"] or [])[:4]]
    queries = queries or [f"residential colleges universities {states} hostel campus"]
    data, _ = llm.ask_json(prompts.DISCOVER_SYSTEM, body, prompts.DISCOVER_SHAPE, max_searches=8,
                           queries=queries, source_limit=30)
    found, seen = [], set()
    for item in data.get("institutions", []):
        name = (item.get("name") or "").strip()
        key = "".join(ch for ch in name.lower() if ch.isalnum())
        if not name or key in seen:
            continue
        seen.add(key)
        found.append(item)
    return found
