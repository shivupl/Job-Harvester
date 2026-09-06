import asyncio
import json
from types import SimpleNamespace

import pytest

from jobwatch.models import Posting
from jobwatch.profile import PROFILE
from jobwatch.score import (SCHEMA, ScorerUnavailable, build_user_message, make_client, score_all,
                            score_posting, validate)

@pytest.fixture(autouse=True)
def fast_sleep(monkeypatch):
    real = asyncio.sleep
    monkeypatch.setattr(asyncio, "sleep", lambda *_: real(0))


ANTHROPIC = {**PROFILE, "provider": "anthropic", "model": "claude-haiku-4-5"}
OPENAI = {**PROFILE, "provider": "openai", "model": "gpt-5.6-luna"}


class FakeMessages:
    def __init__(self, texts):
        self.texts = list(texts)
        self.calls = []

    async def create(self, **kw):
        self.calls.append(kw)
        text = self.texts.pop(0)
        if isinstance(text, Exception):
            raise text
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


class FakeClient:
    def __init__(self, texts):
        self.messages = FakeMessages(texts)


def mk(i=1, desc="x" * 10):
    return Posting(ats="ashby", slug="s", job_id=str(i), title="FDE", company="C", location="SF",
                   remote=None, description=desc, posted_at=None, url="u", comp="$100K")


GOOD = json.dumps({"level": "new_grad", "category": "fde", "location_fit": "bay_area",
                   "years_stated": -1, "fit": 8, "relevance": 9, "reason": "ok"})


async def test_score_posting_sends_schema_and_cached_system_prompt():
    client = FakeClient([GOOD])
    r = await score_posting(client, mk(), ANTHROPIC)
    assert r == {"level": "new_grad", "category": "fde", "location_fit": "bay_area",
                 "years_stated": None, "fit": 8, "relevance": 9, "reason": "ok"}
    kw = client.messages.calls[0]
    assert kw["model"] == "claude-haiku-4-5"
    assert kw["output_config"]["format"]["schema"] == SCHEMA
    assert kw["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "FDE" in kw["messages"][0]["content"] and "$100K" in kw["messages"][0]["content"]


async def test_retries_once_on_garbage_then_none():
    client = FakeClient(["not json", "still not json", "nope"])
    assert await score_posting(client, mk(), ANTHROPIC) is None
    assert len(client.messages.calls) == 3
    client = FakeClient(["garbage", GOOD])
    assert (await score_posting(client, mk(), ANTHROPIC))["fit"] == 8


def test_validate_clamps_and_normalizes():
    out = validate({"level": "weird", "category": "nope", "location_fit": "mars", "years_stated": 3,
                    "fit": 14, "relevance": -3, "reason": "r"})
    assert out == {"level": "unclear", "category": "other", "location_fit": "unknown", "years_stated": 3,
                   "fit": 10, "relevance": 0, "reason": "r"}
    with pytest.raises(ValueError):
        validate({"level": "mid"})


def test_build_user_message_truncates_only_when_asked():
    msg = build_user_message(mk(desc="y" * 10000), 6000)
    assert "y" * 6000 + "\n[truncated]" in msg and "y" * 6001 not in msg
    full = build_user_message(mk(desc="y" * 10000), None)
    assert "y" * 10000 in full and "[truncated]" not in full


async def test_score_all_keys_by_posting_key_and_limits_concurrency():
    client = FakeClient([GOOD, GOOD, "bad", "bad", "bad"])
    res = await score_all(client, [mk(1), mk(2), mk(3)], {**ANTHROPIC, "score_concurrency": 2})
    assert res["ashby:s:1"]["fit"] == 8 and res["ashby:s:2"]["fit"] == 8 and res["ashby:s:3"] is None



class FakeOpenAIChat:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)   # each: (content, finish_reason, refusal) or Exception
        self.calls = []

    async def create(self, **kw):
        self.calls.append(kw)
        o = self.outcomes.pop(0)
        if isinstance(o, Exception):
            raise o
        content, finish, refusal = o
        msg = SimpleNamespace(content=content, refusal=refusal)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason=finish)], model="gpt-5.6-luna")


class FakeOpenAI:
    def __init__(self, outcomes):
        self.chat = SimpleNamespace(completions=FakeOpenAIChat(outcomes))


async def test_openai_call_shape_and_parse():
    client = FakeOpenAI([(GOOD, "stop", None)])
    r = await score_posting(client, mk(), OPENAI)
    assert r["fit"] == 8 and r["category"] == "fde"
    kw = client.chat.completions.calls[0]
    assert kw["model"] == "gpt-5.6-luna"
    assert kw["response_format"]["json_schema"]["schema"] == SCHEMA
    assert kw["response_format"]["json_schema"]["strict"] is True
    assert kw["reasoning_effort"] == "low" and kw["max_completion_tokens"] == 2000
    assert kw["messages"][0]["role"] == "system" and "FDE" in kw["messages"][1]["content"]


async def test_openai_refusal_and_truncation_retry_then_none():
    client = FakeOpenAI([(None, "stop", "I cannot"), ("", "length", None), ("", "length", None)])
    assert await score_posting(client, mk(), OPENAI) is None
    assert len(client.chat.completions.calls) == 3
    client = FakeOpenAI([("", "length", None), (GOOD, "stop", None)])
    assert (await score_posting(client, mk(), OPENAI))["relevance"] == 9


async def test_openai_auth_error_propagates_and_403_returns_none():
    import httpx, openai
    resp = httpx.Response(401, request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"))
    client = FakeOpenAI([openai.AuthenticationError("bad key", response=resp, body=None)])
    with pytest.raises(openai.AuthenticationError):
        await score_posting(client, mk(), OPENAI)
    resp403 = httpx.Response(403, request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"))
    client = FakeOpenAI([openai.PermissionDeniedError("no", response=resp403, body={"error": {"code": "other"}})])
    assert await score_posting(client, mk(), OPENAI) is None
    assert len(client.chat.completions.calls) == 1        # a non-flap 403 is not retried


async def test_model_access_flap_is_retried():
    import httpx, openai
    resp = httpx.Response(403, request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"))
    flap = openai.PermissionDeniedError("no access", response=resp, body={"error": {"code": "model_not_found"}})
    client = FakeOpenAI([flap, (GOOD, "stop", None)])
    assert (await score_posting(client, mk(), OPENAI))["fit"] == 8
    assert len(client.chat.completions.calls) == 2
    client = FakeOpenAI([flap, flap, flap])
    assert await score_posting(client, mk(), OPENAI) is None


async def test_score_all_raises_when_everything_fails():
    client = FakeOpenAI([("", "length", None)] * 15)
    with pytest.raises(ScorerUnavailable):
        await score_all(client, [mk(i) for i in range(5)], OPENAI)
    client = FakeOpenAI([("", "length", None)] * 6)          # fewer than 5 postings: no raise
    res = await score_all(client, [mk(1), mk(2)], OPENAI)
    assert res == {"ashby:s:1": None, "ashby:s:2": None}


def test_make_client_by_provider(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "y")
    import anthropic, openai
    assert isinstance(make_client({**PROFILE, "provider": "openai"}), openai.AsyncOpenAI)
    assert isinstance(make_client({**PROFILE, "provider": "anthropic"}), anthropic.AsyncAnthropic)
    with pytest.raises(ValueError):
        make_client({**PROFILE, "provider": "nope"})
