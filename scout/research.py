"""Step 2: research one institution for signals."""
from datetime import date

from . import config, llm, prompts


def research(inst: dict, params: dict):
    interests = ""
    if params.get("signals_of_interest"):
        interests = "Especially look for: " + "; ".join(params["signals_of_interest"]) + "\n"
    body = prompts.RESEARCH_BODY.format(
        today=date.today().isoformat(),
        name=inst.get("name", ""),
        city=inst.get("city", ""),
        state=inst.get("state", ""),
        type=inst.get("type", ""),
        website=inst.get("website") or "unknown",
        interests=interests,
    )
    q = f'"{inst.get("name", "")}" {inst.get("city", "")}'
    queries = [
        f"{q} tender OR RFQ OR RFP hostel OR \"gate pass\" OR \"access control\" OR biometric",
        f"{q} hostel management system OR \"hostel digitization\" OR ERP",
        f"{q} \"smart campus\" OR \"campus security\" OR \"biometric attendance\"",
        f"{q} number of hostel students hostels capacity residential",
        f"{q} hostel rules outpass OR \"leave register\" OR \"gate pass\" students",
        f"{q} GeM bid tender 2026",
    ]
    if params.get("signals_of_interest"):
        queries.append(f"{q} " + " ".join(params["signals_of_interest"][:2]))
    data, urls = llm.ask_json(prompts.RESEARCH_SYSTEM, body, prompts.RESEARCH_SHAPE,
                              max_searches=config.max_searches(), queries=queries,
                              website=inst.get("website") or "")
    if config.provider() == "gemini":  # label sources using the college's own website
        for sig in data.get("signals", []) or []:
            if sig.get("source_url"):
                sig["source_type"] = llm._source_type(sig["source_url"], inst.get("website") or "")
    return data, urls
