"""Talks to the AI with live web search turned on.

Three providers are supported:
- Groq (default): Groq's free search tools are limited, so the agent runs the web searches itself
  (scout/search.py), gives Groq the result snippets as a numbered list, and Groq reads and judges them.
  Source links come from the search results by construction.
- Google Gemini (default): Google Search grounding. Gemini cannot search and return clean JSON in one
  step, so it works in two steps: (1) search and write notes, (2) turn the notes plus a numbered list of
  the pages it really found into JSON. Every source link therefore comes from the search results,
  never from the AI's memory.
- Anthropic Claude: web search tool, one step.
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from . import config
from .scoring import norm_url


# ------------------------------------------------------------------ shared
def extract_json(text: str):
    text = text or ""
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return None
        candidate = text[start:end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def ask_json(system: str, body: str, shape: str, max_searches: int = 6, queries=None, website: str = "", source_limit: int = 24):
    """Runs a web-searching research task. Returns (parsed_json, set_of_verified_urls).

    `queries` are the web searches to run for providers that do not search by themselves (Groq)."""
    key = config.api_key()
    if not key:
        raise RuntimeError(
            f"No API key found. Open config.env, paste your key, save, and restart the agent."
        )
    if config.provider() == "groq":
        return _groq(key, system, body, shape, queries or [], website, source_limit)
    if config.provider() == "gemini":
        return _gemini(key, system, body, shape)
    return _claude(key, system, body, shape, max_searches)


# ------------------------------------------------------------------ Groq
_GROQ_PREFERRED = ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "openai/gpt-oss-20b"]
_groq_model_cache = {}


def _groq_pick_model(client) -> str:
    names = {getattr(m, "id", "") for m in client.models.list().data}
    for name in _GROQ_PREFERRED:
        if name in names:
            return name
    raise RuntimeError("None of the usual Groq models are available to this key. Set GROQ_MODEL in config.env "
                       "to a model name from console.groq.com/docs/models.")


def _groq_call(client, system, user, max_out=3500):
    """One Groq call with patience for rate limits and automatic model switch if a model is retired."""
    import time

    import groq

    model = _groq_model_cache.get(config.model(), config.model())
    last = None
    for attempt in range(6):
        kwargs = dict(model=model, temperature=0.1, max_completion_tokens=max_out,
                      messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        if "gpt-oss" in model:
            kwargs["reasoning_effort"] = "low"
        try:
            try:
                return client.chat.completions.create(response_format={"type": "json_object"}, **kwargs)
            except groq.BadRequestError as exc:
                if "json" in str(exc).lower() and "request too large" not in str(exc).lower():
                    return client.chat.completions.create(**kwargs)  # model without JSON mode
                raise
        except groq.RateLimitError as exc:
            last = exc
            wait = 20.0
            try:
                wait = float(exc.response.headers.get("retry-after", wait))
            except Exception:
                pass
            time.sleep(min(max(wait, 5.0), 90.0))
        except groq.NotFoundError as exc:
            last = exc
            new = _groq_pick_model(client)
            if new == model:
                raise
            _groq_model_cache[config.model()] = model = new
    raise last


def _groq_prompt(body, shape, sources, notes_limit):
    listing = "\n".join(
        f"[{i + 1}] {s['title'][:90]} ({domain_of(s['url'])}): {s['snippet'][:notes_limit]}"
        for i, s in enumerate(sources)) or "(no search results)"
    return (
        f"TASK:\n{body}\n\nSEARCH RESULTS (numbered). These are all the evidence you have:\n{listing}\n\n"
        "Use only these search results. Wherever the shape has \"source_url\", give instead "
        "\"source_index\": the integer number of the result that supports that signal. If no result supports a "
        "signal, leave it out. Do not guess dates, numbers or sources; use null or \"unknown\" when the results "
        "do not say. Reply with one JSON object only.\n\nJSON shape:\n"
        + shape.replace('"source_url": "", "source_title": "", ', '"source_index": 0, ')
    )


def domain_of(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _groq(key, system, body, shape, queries, website, source_limit=24):
    import groq

    from . import search

    sources = search.gather(queries, limit=source_limit)
    if not sources:
        raise RuntimeError(
            "Web search returned nothing (DuckDuckGo may be limiting requests right now). Wait a few minutes "
            "and try again, or add a free Tavily key as TAVILY_API_KEY in config.env."
        )
    client = groq.Groq(api_key=key, max_retries=2)

    text = None
    for limit_sources, snippet_chars in ((source_limit, 320), (14, 240), (8, 180)):  # shrink if the request is too large
        prompt = _groq_prompt(body, shape, sources[:limit_sources], snippet_chars)
        try:
            resp = _groq_call(client, system, prompt)
            text = resp.choices[0].message.content or ""
            break
        except groq.APIStatusError as exc:
            if exc.status_code in (413, 429) and "tokens" in str(exc).lower() and limit_sources > 8:
                continue
            raise
    data = extract_json(text or "")
    if data is None:
        raise RuntimeError("The AI answer could not be read. Try again.")

    used = sources[:limit_sources]
    attach = [{"url": s["url"], "title": s["title"], "redirect": s["url"]} for s in used]
    _attach_sources(data, attach, website)
    return data, {norm_url(s["url"]) for s in used}


# ------------------------------------------------------------------ Gemini
_OFFICIAL_SUFFIXES = (".ac.in", ".edu", ".edu.in", ".gov.in", ".nic.in", ".gov")
_PORTAL_HINTS = ("gem.gov.in", "eprocure", "etenders", "tender", "cppp")


def _source_type(url: str, website: str = "") -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    if any(h in host for h in _PORTAL_HINTS):
        return "portal"
    if host.endswith(_OFFICIAL_SUFFIXES):
        return "official"
    site = urlparse(website or "").netloc.lower().removeprefix("www.")
    if site and (host == site or host.endswith("." + site)):
        return "official"
    return "news"


def _attach_sources(data, sources, website=""):
    """Replace each signal's source_index with the real link from the numbered list."""
    for sig in data.get("signals", []) or []:
        try:
            src = sources[int(sig.get("source_index")) - 1]
        except (TypeError, ValueError, IndexError):
            sig["source_url"] = ""
            continue
        sig["source_url"] = src["url"]
        sig["source_title"] = src["title"]
        sig["source_type"] = _source_type(src["url"], website)


def _resolve(uri: str) -> str:
    """Google gives redirect links for search results; follow them to the real page address."""
    try:
        import httpx

        with httpx.Client(follow_redirects=True, timeout=10) as c:
            try:
                r = c.head(uri)
                if r.status_code >= 400 or str(r.url) == uri:
                    r = c.get(uri)
            except Exception:
                r = c.get(uri)
            final = str(r.url)
            return final if final and "vertexaisearch.cloud.google.com" not in final else uri
    except Exception:
        return uri


def _gemini_sources(resp):
    chunks = []
    for cand in getattr(resp, "candidates", None) or []:
        meta = getattr(cand, "grounding_metadata", None)
        for ch in (getattr(meta, "grounding_chunks", None) or []):
            web = getattr(ch, "web", None)
            if web and getattr(web, "uri", None):
                chunks.append((web.uri, getattr(web, "title", "") or getattr(web, "domain", "") or ""))
    seen, uniq = set(), []
    for uri, title in chunks:
        if uri not in seen:
            seen.add(uri)
            uniq.append((uri, title))
    uniq = uniq[:25]
    with ThreadPoolExecutor(max_workers=6) as pool:
        finals = list(pool.map(lambda t: _resolve(t[0]), uniq))
    return [{"redirect": u, "url": f, "title": t} for (u, t), f in zip(uniq, finals)]


_picked_model = {}


def _pick_newest_flash(client) -> str:
    """Ask Google which models this key can use and choose the newest 'flash' one."""
    best, best_ver = None, -1.0
    for m in client.models.list():
        name = (getattr(m, "name", "") or "").removeprefix("models/")
        actions = getattr(m, "supported_actions", None) or []
        mm = re.fullmatch(r"gemini-(\d+(?:\.\d+)?)-flash", name)
        if mm and (not actions or "generateContent" in actions) and float(mm.group(1)) > best_ver:
            best, best_ver = name, float(mm.group(1))
    if not best:
        raise RuntimeError("No usable Gemini flash model was found for this key. Set GEMINI_MODEL in config.env.")
    return best


def _generate(client, model, **kwargs):
    """Call Gemini; if the model name has been retired, switch to the newest available one."""
    model = _picked_model.get(model, model)
    try:
        return client.models.generate_content(model=model, **kwargs)
    except Exception as exc:
        low = str(exc).lower()
        if "404" in low or "not_found" in low or "no longer available" in low:
            new = _pick_newest_flash(client)
            if new != model:
                _picked_model[config.model()] = new
                return client.models.generate_content(model=new, **kwargs)
        raise


def _gemini(key, system, body, shape):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=key)
    model = config.model()

    # Step 1: search and write notes
    notes_prompt = (
        body
        + "\n\nSearch the web thoroughly. Reply with plain-text research notes only (no JSON): every finding "
          "with its date and the website it came from, any numbers such as hostel size, and your ratings "
          "with one-line reasons for anything the task asks you to rate. Say plainly what you could not find."
    )
    r1 = _generate(
        client, model,
        contents=notes_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )
    notes = r1.text or ""
    sources = _gemini_sources(r1)

    # Step 2: turn the notes into JSON; sources are chosen by number from the real list
    listing = "\n".join(f"[{i + 1}] {s['title']} - {s['url']}" for i, s in enumerate(sources)) or "(none found)"
    json_prompt = (
        f"TASK:\n{body}\n\nRESEARCH NOTES:\n{notes}\n\nSOURCES FOUND (numbered):\n{listing}\n\n"
        "Using only the notes and the sources, produce the JSON described below. Wherever the shape has "
        "\"source_url\", give instead \"source_index\": the integer number of the source above that supports "
        "that signal. If no listed source supports a signal, leave that signal out. Never invent sources, "
        "dates or numbers.\n\nJSON shape:\n" + shape.replace('"source_url": "", "source_title": "", ',
                                                              '"source_index": 0, ')
    )
    r2 = _generate(
        client, model,
        contents=json_prompt,
        config=types.GenerateContentConfig(
            system_instruction="Return ONLY a valid JSON object. No commentary.",
            response_mime_type="application/json",
        ),
    )
    data = extract_json(r2.text or "")
    if data is None:
        raise RuntimeError("The AI answer could not be read. Try again.")

    _attach_sources(data, sources)
    urls = set()
    for s in sources:
        urls.add(norm_url(s["url"]))
        urls.add(norm_url(s["redirect"]))
    return data, urls


# ------------------------------------------------------------------ Claude
def _claude_collect_urls(resp, urls: set):
    for block in resp.content:
        kind = getattr(block, "type", "")
        if kind == "web_search_tool_result":
            content = getattr(block, "content", None)
            if isinstance(content, list):
                for item in content:
                    url = getattr(item, "url", None)
                    if url:
                        urls.add(norm_url(url))
        elif kind == "text":
            for cite in getattr(block, "citations", None) or []:
                url = getattr(cite, "url", None)
                if url:
                    urls.add(norm_url(url))


def _claude(key, system, body, shape, max_searches):
    from anthropic import Anthropic

    client = Anthropic(api_key=key, max_retries=6)
    model = config.model()
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": max_searches}]
    messages = [{"role": "user", "content": body + "\n\nJSON shape:\n" + shape}]
    urls: set = set()
    text = ""
    for _ in range(6):
        resp = client.messages.create(model=model, max_tokens=8000, system=system, messages=messages, tools=tools)
        _claude_collect_urls(resp, urls)
        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        break
    data = extract_json(text)
    if data is None:
        repair = client.messages.create(
            model=model, max_tokens=8000, system="Return ONLY valid JSON. No commentary.",
            messages=[{"role": "user", "content": "Convert this into the JSON object that was requested, "
                                                  "keeping all facts unchanged:\n\n" + text}])
        data = extract_json("".join(b.text for b in repair.content if getattr(b, "type", "") == "text"))
    if data is None:
        raise RuntimeError("The AI answer could not be read. Try again.")
    return data, urls
