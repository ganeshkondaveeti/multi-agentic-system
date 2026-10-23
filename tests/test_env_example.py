"""The env templates are committed to a public repo, so their secrets stay blank."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SECRETS = ("GROQ_API_KEY", "GEMINI_API_KEY", "ACCESS_CODE")


def _values(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


@pytest.mark.parametrize("name", SECRETS)
def test_root_template_leaves_secrets_blank(name):
    values = _values(ROOT / ".env.example")
    assert name in values
    assert values[name] == "", f"{name} has a value in .env.example; put it in .env"


def test_web_template_holds_no_secrets():
    values = _values(ROOT / "web" / ".env.example")
    assert set(values) == {"VITE_API_BASE_URL"}
