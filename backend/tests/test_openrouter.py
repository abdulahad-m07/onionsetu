# backend/tests/test_openrouter.py
"""Unit tests for the OpenRouter server-side batch assessment adapter.

All HTTP is mocked via httpx.MockTransport — no test calls the real
OpenRouter API, and no live key is required.
"""
import base64
import io
import json

import httpx
import pytest
from PIL import Image

from backend.app.services import openrouter_service as or_mod
from backend.app.services.openrouter_service import (
    OpenRouterAPIError,
    OpenRouterAuthError,
    OpenRouterConfigError,
    OpenRouterResponseError,
    OpenRouterService,
    OpenRouterTimeoutError,
)


@pytest.fixture(autouse=True)
def _dummy_server_key(monkeypatch):
    # Adapter tests must never depend on a real key; the missing-key case
    # overrides this per-test. monkeypatch auto-restores afterwards.
    monkeypatch.setattr(or_mod.settings, "OPENROUTER_API_KEY", "test-key")


def _mock_client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _openai_text_response(assessment: dict):
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(assessment),
                },
                "finish_reason": "stop",
            }
        ],
    }


def _ok_assessment():
    return {
        "batch_assessment": "Batch shows mostly uniform bulbs with minor skin blemishes.",
        "observations": ["Uniform size across views", "Minor skin blemishes visible"],
        "visible_quality_issues": [
            {"issue": "Skin blemishes", "severity": "low", "evidence_ref": "image 1"}
        ],
        "uncertainty_notes": None,
        "assessment_confidence": 0.87,
        "suggested_grade": "B",
        "review_required": False,
        "images_analyzed": 2,
    }


def _tiny_jpeg() -> bytes:
    img = Image.new("RGB", (64, 48), color=(190, 120, 60))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_successful_structured_response_parsed():
    def handler(request: httpx.Request):
        return httpx.Response(200, json=_openai_text_response(_ok_assessment()))

    parsed = await OpenRouterService.assess_batch(
        [_tiny_jpeg(), _tiny_jpeg()],
        "evidence summary",
        client=_mock_client(handler),
    )
    assessment = parsed["assessment"]
    assert assessment.batch_assessment.startswith("Batch shows")
    assert assessment.assessment_confidence == 0.87
    assert assessment.suggested_grade is not None
    assert assessment.suggested_grade.value == "B"
    assert assessment.review_required is False
    assert assessment.images_analyzed == 2  # pipeline fact, not model claim
    assert len(assessment.visible_quality_issues) == 1
    assert parsed["warnings"] == []


@pytest.mark.asyncio
async def test_request_uses_bearer_key_images_and_schema(monkeypatch):
    monkeypatch.setattr(or_mod.settings, "OPENROUTER_API_KEY", "server-secret")
    monkeypatch.setattr(
        or_mod.settings, "OPENROUTER_MODEL_ID", "qwen/qwen2.5-vl-72b-instruct:free"
    )

    seen = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_openai_text_response(_ok_assessment()))

    await OpenRouterService.assess_batch(
        [_tiny_jpeg()], "evidence", client=_mock_client(handler)
    )

    assert seen["url"].endswith("/chat/completions")
    assert "server-secret" not in seen["url"]
    assert seen["headers"]["authorization"] == "Bearer server-secret"
    assert "server-secret" not in json.dumps(seen["body"])
    assert seen["body"]["model"] == "qwen/qwen2.5-vl-72b-instruct:free"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    messages = seen["body"]["messages"]
    assert messages[0]["role"] == "system"
    user_parts = messages[1]["content"]
    assert user_parts[0]["type"] == "text"
    assert user_parts[0]["text"].startswith("Assess this onion procurement batch")
    assert "JSON" in user_parts[0]["text"]  # required for json_object mode
    inline = [p for p in user_parts[1:] if p.get("type") == "image_url"]
    assert len(inline) == 1
    assert inline[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    base64.b64decode(inline[0]["image_url"]["url"].split(",", 1)[1])  # valid b64


@pytest.mark.asyncio
async def test_missing_key_never_hits_network(monkeypatch):
    monkeypatch.setattr(or_mod.settings, "OPENROUTER_API_KEY", "")

    def handler(request: httpx.Request):  # pragma: no cover
        raise AssertionError("network must not be touched without a key")

    with pytest.raises(OpenRouterConfigError):
        await OpenRouterService.assess_batch(
            [_tiny_jpeg()], "evidence", client=_mock_client(handler)
        )


@pytest.mark.asyncio
async def test_empty_choices_is_malformed():
    def handler(request: httpx.Request):
        return httpx.Response(200, json={"choices": []})

    with pytest.raises(OpenRouterResponseError):
        await OpenRouterService.assess_batch(
            [_tiny_jpeg()], "evidence", client=_mock_client(handler)
        )


@pytest.mark.asyncio
async def test_truncated_finish_reason_is_malformed():
    assessment = json.dumps(_ok_assessment())
    for bad_finish in ("length", "content_filter", None):
        def handler(request: httpx.Request, _a=assessment):
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {"role": "assistant", "content": _a},
                            "finish_reason": bad_finish,
                        }
                    ]
                },
            )

        with pytest.raises(OpenRouterResponseError):
            await OpenRouterService.assess_batch(
                [_tiny_jpeg()], "evidence", client=_mock_client(handler)
            )


@pytest.mark.asyncio
async def test_error_payload_is_malformed():
    def handler(request: httpx.Request):
        return httpx.Response(
            200, json={"error": {"message": "No endpoints found", "code": 404}}
        )

    with pytest.raises(OpenRouterResponseError):
        await OpenRouterService.assess_batch(
            [_tiny_jpeg()], "evidence", client=_mock_client(handler)
        )


@pytest.mark.asyncio
async def test_non_json_text_is_malformed():
    def handler(request: httpx.Request):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "Grade is B, trust me"},
                        "finish_reason": "stop",
                    }
                ]
            },
        )

    with pytest.raises(OpenRouterResponseError):
        await OpenRouterService.assess_batch(
            [_tiny_jpeg()], "evidence", client=_mock_client(handler)
        )


@pytest.mark.asyncio
async def test_schema_violation_is_malformed():
    bad = _ok_assessment()
    del bad["batch_assessment"]  # required field missing

    def handler(request: httpx.Request):
        return httpx.Response(200, json=_openai_text_response(bad))

    with pytest.raises(OpenRouterResponseError):
        await OpenRouterService.assess_batch(
            [_tiny_jpeg()], "evidence", client=_mock_client(handler)
        )


@pytest.mark.asyncio
async def test_invalid_suggested_grade_discarded_with_forced_review():
    bad = _ok_assessment()
    bad["suggested_grade"] = "A+"

    def handler(request: httpx.Request):
        return httpx.Response(200, json=_openai_text_response(bad))

    parsed = await OpenRouterService.assess_batch(
        [_tiny_jpeg()], "evidence", client=_mock_client(handler)
    )
    # Assessment preserved; ONLY the untrusted suggestion is dropped.
    assert parsed["assessment"].suggested_grade is None
    assert parsed["assessment"].review_required is True
    assert any("suggested_grade" in w for w in parsed["warnings"])
    assert parsed["assessment"].assessment_confidence == 0.87


@pytest.mark.asyncio
async def test_observations_string_wrapped_verbatim_as_single_item():
    # Real Qwen behavior: observations returned as plain text instead of an
    # array. The text must survive verbatim — not split, not invented.
    text = "Four onions are visible, uniform bulbs, minor surface irregularities."
    ok = _ok_assessment()
    ok["observations"] = text

    def handler(request: httpx.Request):
        return httpx.Response(200, json=_openai_text_response(ok))

    parsed = await OpenRouterService.assess_batch(
        [_tiny_jpeg()], "evidence", client=_mock_client(handler)
    )
    assert parsed["assessment"].observations == [text]


@pytest.mark.asyncio
async def test_observations_blank_string_becomes_empty_list():
    ok = _ok_assessment()
    ok["observations"] = "   "

    def handler(request: httpx.Request):
        return httpx.Response(200, json=_openai_text_response(ok))

    parsed = await OpenRouterService.assess_batch(
        [_tiny_jpeg()], "evidence", client=_mock_client(handler)
    )
    assert parsed["assessment"].observations == []


@pytest.mark.asyncio
async def test_malformed_observations_types_rejected():
    for bad_value in (42, {"text": "x"}, [["nested"]]):
        ok = _ok_assessment()
        ok["observations"] = bad_value

        def handler(request: httpx.Request, _ok=ok):
            return httpx.Response(200, json=_openai_text_response(_ok))

        with pytest.raises(OpenRouterResponseError):
            await OpenRouterService.assess_batch(
                [_tiny_jpeg()], "evidence", client=_mock_client(handler)
            )


@pytest.mark.asyncio
async def test_issues_description_alias_mapped_verbatim():
    # Real Qwen behavior: issue objects use `description`, not `issue`.
    # The text must survive verbatim under the stable contract field.
    ok = _ok_assessment()
    ok["visible_quality_issues"] = [
        {
            "severity": "medium",
            "description": "Discoloration on the skin",
            "evidence_ref": "image 1",
        }
    ]

    def handler(request: httpx.Request):
        return httpx.Response(200, json=_openai_text_response(ok))

    parsed = await OpenRouterService.assess_batch(
        [_tiny_jpeg()], "evidence", client=_mock_client(handler)
    )
    issues = parsed["assessment"].visible_quality_issues
    assert len(issues) == 1
    assert issues[0].issue == "Discoloration on the skin"
    assert issues[0].severity.value == "medium"
    assert issues[0].evidence_ref == "image 1"


@pytest.mark.asyncio
async def test_issues_explicit_issue_key_wins_over_alias():
    ok = _ok_assessment()
    ok["visible_quality_issues"] = [
        {"issue": "Real issue", "description": "Other text", "severity": "high"}
    ]

    def handler(request: httpx.Request):
        return httpx.Response(200, json=_openai_text_response(ok))

    parsed = await OpenRouterService.assess_batch(
        [_tiny_jpeg()], "evidence", client=_mock_client(handler)
    )
    assert parsed["assessment"].visible_quality_issues[0].issue == "Real issue"


@pytest.mark.asyncio
async def test_issues_missing_both_keys_rejected():
    ok = _ok_assessment()
    ok["visible_quality_issues"] = [{"severity": "low"}]

    def handler(request: httpx.Request):
        return httpx.Response(200, json=_openai_text_response(ok))

    with pytest.raises(OpenRouterResponseError):
        await OpenRouterService.assess_batch(
            [_tiny_jpeg()], "evidence", client=_mock_client(handler)
        )


@pytest.mark.asyncio
async def test_urs_counts_pass_through_when_consistent():
    ok = _ok_assessment()
    ok["urs_onions"] = 12
    ok["assessed_onions"] = 150

    def handler(request: httpx.Request):
        return httpx.Response(200, json=_openai_text_response(ok))

    parsed = await OpenRouterService.assess_batch(
        [_tiny_jpeg()], "evidence", client=_mock_client(handler)
    )
    assert parsed["assessment"].urs_onions == 12
    assert parsed["assessment"].assessed_onions == 150


@pytest.mark.asyncio
async def test_inconsistent_urs_counts_rejected_whole_response():
    # urs > assessed is impossible evidence: the response is unusable,
    # so the whole assessment is rejected (never silently repaired).
    ok = _ok_assessment()
    ok["urs_onions"] = 200
    ok["assessed_onions"] = 150

    def handler(request: httpx.Request):
        return httpx.Response(200, json=_openai_text_response(ok))

    with pytest.raises(OpenRouterResponseError):
        await OpenRouterService.assess_batch(
            [_tiny_jpeg()], "evidence", client=_mock_client(handler)
        )


@pytest.mark.asyncio
async def test_negative_urs_counts_rejected():
    ok = _ok_assessment()
    ok["urs_onions"] = -1
    ok["assessed_onions"] = 150

    def handler(request: httpx.Request):
        return httpx.Response(200, json=_openai_text_response(ok))

    with pytest.raises(OpenRouterResponseError):
        await OpenRouterService.assess_batch(
            [_tiny_jpeg()], "evidence", client=_mock_client(handler)
        )


@pytest.mark.asyncio
async def test_confidence_out_of_range_rejected():
    bad = _ok_assessment()
    bad["assessment_confidence"] = 9.9  # impossible: must not become output

    def handler(request: httpx.Request):
        return httpx.Response(200, json=_openai_text_response(bad))

    with pytest.raises(OpenRouterResponseError):
        await OpenRouterService.assess_batch(
            [_tiny_jpeg()], "evidence", client=_mock_client(handler)
        )


@pytest.mark.asyncio
async def test_timeout_maps_to_timeout_error():
    def handler(request: httpx.Request):
        raise httpx.ConnectTimeout("slow upstream")

    with pytest.raises(OpenRouterTimeoutError):
        await OpenRouterService.assess_batch(
            [_tiny_jpeg()], "evidence", client=_mock_client(handler)
        )


@pytest.mark.asyncio
async def test_server_error_maps_to_api_error():
    def handler(request: httpx.Request):
        return httpx.Response(500, text="upstream exploded")

    with pytest.raises(OpenRouterAPIError):
        await OpenRouterService.assess_batch(
            [_tiny_jpeg()], "evidence", client=_mock_client(handler)
        )


@pytest.mark.asyncio
async def test_rate_limit_maps_to_api_error_with_status():
    def handler(request: httpx.Request):
        return httpx.Response(429, json={"error": {"message": "rate limited"}})

    with pytest.raises(OpenRouterAPIError) as exc_info:
        await OpenRouterService.assess_batch(
            [_tiny_jpeg()], "evidence", client=_mock_client(handler)
        )
    assert exc_info.value.upstream_status == 429


@pytest.mark.asyncio
async def test_invalid_key_maps_to_auth_error():
    def handler(request: httpx.Request):
        return httpx.Response(401, json={"error": {"message": "Invalid API key"}})

    with pytest.raises(OpenRouterAuthError):
        await OpenRouterService.assess_batch(
            [_tiny_jpeg()], "evidence", client=_mock_client(handler)
        )


def test_normalize_image_caps_dimensions_and_strips_to_jpeg():
    big = Image.new("RGB", (3000, 2000), color=(200, 100, 50))
    buf = io.BytesIO()
    big.save(buf, format="PNG")
    out = OpenRouterService.normalize_image(buf.getvalue())
    with Image.open(io.BytesIO(out)) as decoded:
        assert decoded.format == "JPEG"
        assert max(decoded.size) <= or_mod.settings.OPENROUTER_MAX_IMAGE_DIM


def test_normalize_image_rejects_garbage():
    with pytest.raises(ValueError):
        OpenRouterService.normalize_image(b"not-an-image")


@pytest.mark.asyncio
async def test_too_many_images_rejected_without_network():
    def handler(request: httpx.Request):  # pragma: no cover
        raise AssertionError("unreachable")

    with pytest.raises(ValueError):
        await OpenRouterService.assess_batch(
            [_tiny_jpeg()] * (or_mod.settings.OPENROUTER_MAX_IMAGES + 1),
            "evidence",
            client=_mock_client(handler),
        )
