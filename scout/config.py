"""Settings. Reads config.env in the main folder."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / "config.env"
DATA_DIR = ROOT / "data"
RUNS_DIR = DATA_DIR / "runs"

DEFAULT_MODELS = {
    "groq": "openai/gpt-oss-120b",
    "gemini": "gemini-3.8-flash",
    "anthropic": "claude-sonnet-5-5",
}
KEY_VARS = {"groq": "GROQ_API_KEY", "gemini": "GOOGLE_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
NAMES = {"groq": "Groq", "gemini": "Google Gemini", "anthropic": "Anthropic Claude"}
MODEL_VARS = {"groq": "GROQ_MODEL", "gemini": "GEMINI_MODEL", "anthropic": "CLAUDE_MODEL"}


def _load():
    load_dotenv(ENV_FILE, override=True)


def provider() -> str:
    """'groq' (default), 'gemini' or 'anthropic'."""
    _load()
    p = os.getenv("PROVIDER", "groq").strip().lower()
    return p if p in DEFAULT_MODELS else "groq"


def provider_name() -> str:
    return NAMES[provider()]


def key_var() -> str:
    return KEY_VARS[provider()]


def _clean(value: str) -> str:
    v = (value or "").strip().strip('"').strip("'")
    return "" if (not v or v.startswith("PASTE_YOUR")) else v


def api_key() -> str:
    """The key for the chosen provider, or '' if missing / still the placeholder."""
    _load()
    return _clean(os.getenv(key_var(), ""))


def key_problem() -> str:
    """A plain-words reason the key looks wrong, or '' if it looks fine."""
    key = api_key()
    if not key:
        return ""
    p = provider()
    if p == "groq" and not key.startswith("gsk_"):
        return ("Groq keys start with gsk_. Create one at console.groq.com/keys and paste it after "
                "GROQ_API_KEY= in config.env.")
    if p == "anthropic" and not key.startswith("sk-ant-"):
        return "Anthropic keys start with sk-ant-. Check the key after ANTHROPIC_API_KEY=."
    if p != "anthropic" and key.startswith("sk-ant-"):
        return f"That is an Anthropic key, but PROVIDER is {p}. Paste the right key after {key_var()}=."
    return ""


def model() -> str:
    _load()
    return os.getenv(MODEL_VARS[provider()], "").strip() or DEFAULT_MODELS[provider()]


def tavily_key() -> str:
    """Optional better web search. Leave blank to use free DuckDuckGo search."""
    _load()
    return _clean(os.getenv("TAVILY_API_KEY", ""))


def max_searches() -> int:
    """Claude only. Gemini and Groq setups choose their own searches."""
    _load()
    try:
        return max(1, min(15, int(os.getenv("MAX_SEARCHES_PER_COLLEGE", "6"))))
    except ValueError:
        return 6


def parallel() -> int:
    _load()
    default = "1" if provider() == "groq" else "2"  # Groq's free plan allows few tokens per minute
    try:
        return max(1, min(8, int(os.getenv("PARALLEL_COLLEGES", default))))
    except ValueError:
        return int(default)


RUNS_DIR.mkdir(parents=True, exist_ok=True)
