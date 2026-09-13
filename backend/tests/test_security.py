# backend/tests/test_security.py
"""Repository-level security invariants (no live secrets, no client keys).

These tests assert structural guarantees, not secret values:
- the committed env TEMPLATE carries names only (empty placeholders);
- no provider key identifier appears anywhere under frontend/;
- error responses never echo a configured key value.
"""
import json
import pathlib

import pytest
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
FORBIDDEN_IN_FLUTTER = ("GEMINI_API_KEY", "OPENROUTER_API_KEY", "ROBOFLOW_API_KEY", "x-goog-api-key")


def _read_template_value(path: pathlib.Path, name: str) -> str | None:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(name + "="):
            return line.split("=", 1)[1].strip()
    return None


def test_env_example_has_names_only():
    template = REPO_ROOT / ".env.example"
    assert template.exists()
    for name in ("ROBOFLOW_API_KEY", "OPENROUTER_API_KEY"):
        assert _read_template_value(template, name) == "", (
            f".env.example must carry only the {name} NAME with an empty value"
        )
    for line in template.read_text(encoding="utf-8").splitlines():
        assert not line.strip().startswith("GEMINI_API_KEY="), (
            ".env.example must not reference the retired Gemini provider"
        )
    assert "PUBLIC_BASE_URL" in template.read_text(encoding="utf-8")


def test_gitignore_covers_env_files():
    ignored = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in ignored
    assert "backend/.env" in ignored


def test_no_provider_key_references_in_flutter():
    hits = []
    # Production sources only: test files legitimately MENTION these markers
    # when asserting their absence (e.g. header-credential tests).
    lib_root = REPO_ROOT / "frontend" / "lib"
    for path in lib_root.rglob("*.dart"):
        text = path.read_text(encoding="utf-8")
        for marker in FORBIDDEN_IN_FLUTTER:
            if marker in text:
                hits.append(f"{path.relative_to(REPO_ROOT)}: {marker}")
    assert hits == [], f"provider credentials referenced in Flutter: {hits}"


@pytest.mark.asyncio
async def test_error_paths_never_carry_key_values(monkeypatch):
    from backend.app.services import openrouter_service as or_mod

    sentinel = "SENTINEL-KEY-VALUE-12345"
    monkeypatch.setattr(or_mod.settings, "OPENROUTER_API_KEY", sentinel)

    # Request construction embeds the key ONLY in the Authorization header,
    # never in the URL or JSON body that could land in logs.
    request = or_mod.OpenRouterService.build_request(
        [("image/jpeg", "aGk=")], "evidence"
    )
    assert request["headers"]["Authorization"] == f"Bearer {sentinel}"
    assert sentinel not in request["url"]
    assert sentinel not in json.dumps(request["body"])

    # And the missing-key error carries no value at all.
    monkeypatch.setattr(or_mod.settings, "OPENROUTER_API_KEY", "")
    with pytest.raises(or_mod.OpenRouterConfigError) as exc_info:
        or_mod.OpenRouterService.build_request([("image/jpeg", "aGk=")], "evidence")
    assert sentinel not in str(exc_info.value)
