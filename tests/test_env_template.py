"""Guards the .env.example template so new setups never miss a required setting."""

from pathlib import Path

REQUIRED_KEYS = {
    "GOOGLE_API_KEY",
    "ATLAS_PRIMARY_MODEL",
    "ATLAS_FALLBACK_MODELS",
    "GOOGLE_OAUTH_CLIENT_FILE",
    "GOOGLE_TOKEN_FILE",
    "ATLAS_ALLOWED_RECIPIENT_DOMAIN",
}


def _template_keys() -> set[str]:
    text = (Path(__file__).resolve().parents[1] / ".env.example").read_text()
    return {
        line.split("=", 1)[0].strip()
        for line in text.splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    }


def test_env_template_lists_required_keys() -> None:
    missing = REQUIRED_KEYS - _template_keys()
    assert not missing, f".env.example is missing: {sorted(missing)}"
