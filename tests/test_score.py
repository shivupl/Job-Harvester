import json
from types import SimpleNamespace

import pytest

from jobwatch.models import Posting
from jobwatch.profile import PROFILE
from jobwatch.score import SCHEMA, build_user_message, score_all, score_posting, validate


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


GOOD = json.dumps({"level": "new_grad", "new_grad_fit": 0.9, "years_stated": -1, "score": 8, "reason": "ok"})


async def test_score_posting_sends_schema_and_cached_system_prompt():
    client = FakeClient([GOOD])
    r = await score_posting(client, mk(), PROFILE)
    assert r == {"level": "new_grad", "new_grad_fit": 0.9, "years_stated": None, "score": 8, "reason": "ok"}
    kw = client.messages.calls[0]
    assert kw["model"] == "claude-haiku-4-5"
    assert kw["output_config"]["format"]["schema"] == SCHEMA
    assert kw["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "FDE" in kw["messages"][0]["content"] and "$100K" in kw["messages"][0]["content"]


async def test_retries_once_on_garbage_then_none():
    client = FakeClient(["not json", "still not json"])
    assert await score_posting(client, mk(), PROFILE) is None
    assert len(client.messages.calls) == 2
    client = FakeClient(["garbage", GOOD])
    assert (await score_posting(client, mk(), PROFILE))["score"] == 8


def test_validate_clamps_and_normalizes():
    out = validate({"level": "weird", "new_grad_fit": 1.7, "years_stated": 3, "score": 14, "reason": "r"})
    assert out == {"level": "unclear", "new_grad_fit": 1.0, "years_stated": 3, "score": 10, "reason": "r"}
    with pytest.raises(ValueError):
        validate({"level": "mid"})


def test_build_user_message_truncates():
    msg = build_user_message(mk(desc="y" * 10000), 6000)
    assert "y" * 6000 + "\n[truncated]" in msg and "y" * 6001 not in msg


async def test_score_all_keys_by_posting_key_and_limits_concurrency():
    client = FakeClient([GOOD, GOOD, "bad", "bad"])
    res = await score_all(client, [mk(1), mk(2), mk(3)], {**PROFILE, "score_concurrency": 2})
    assert res["ashby:s:1"]["score"] == 8 and res["ashby:s:2"]["score"] == 8 and res["ashby:s:3"] is None
