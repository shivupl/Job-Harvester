"""Claude scoring with structured outputs. One call per prefilter survivor."""
from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

import anthropic

from .models import Posting
from .profile import PROFILE

LEVELS = ["new_grad", "junior", "mid", "senior", "unclear"]

SCHEMA = {
    "type": "object",
    "properties": {
        "level": {"type": "string", "enum": LEVELS},
        "new_grad_fit": {"type": "number"},
        "years_stated": {"type": "integer"},
        "score": {"type": "integer"},
        "reason": {"type": "string"},
    },
    "required": ["level", "new_grad_fit", "years_stated", "score", "reason"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = f"""You screen job postings for one specific candidate and return strict JSON.

Candidate: {PROFILE["candidate"]}

Read the whole posting. Titles lie; the body tells you the real level. Decide:

- level: the seniority the posting actually wants. "new_grad" if it explicitly welcomes new grads or 0-1 years. "junior" for 1-2 years or an early-career framing. "mid" when responsibilities or requirements imply 3-5 years even if the title is neutral. "senior" for 5+ years, ownership of teams or systems, mentoring. "unclear" only when the body gives no signal.
- new_grad_fit: 0.0-1.0 probability that this candidate could realistically be hired into this role.
- years_stated: the minimum years of experience the posting states, or -1 if none is stated.
- score: 0-10 for this candidate, calibrated as follows.
  9-10: clearly open to new grads or 0-2 years, a product/founding/FDE/solutions/applied-AI builder role, Bay Area or US-remote.
  6-8: plausible for a strong new grad; level not stated or early-career; minor mismatch on role type or location.
  3-5: reads as mid-level despite a neutral title, or the role type is a stretch (pure research, pure infra, non-engineering).
  0-2: senior in substance, wrong function, or wrong region.
  Penalize implied seniority even when the title sounds junior. Do not reward a role for being at a famous company. Treat "founding engineer" as open unless the body says otherwise.
- reason: at most 15 words, specific to this posting, no fluff.

Return only the JSON object."""


def build_user_message(p: Posting, max_chars: int) -> str:
    desc = p.description
    if len(desc) > max_chars:
        desc = desc[:max_chars] + "\n[truncated]"
    lines = [
        f"Title: {p.title}",
        f"Company: {p.company}",
        f"Location: {p.location or 'unknown'}",
        f"Remote: {p.remote if p.remote is not None else 'unknown'}",
    ]
    if p.comp:
        lines.append(f"Compensation: {p.comp}")
    lines.append("")
    lines.append(desc)
    return "\n".join(lines)


def validate(data: Any) -> dict:
    if not isinstance(data, dict):
        raise ValueError("not an object")
    for k in ("level", "new_grad_fit", "years_stated", "score", "reason"):
        if k not in data:
            raise ValueError(f"missing {k}")
    level = data["level"] if data["level"] in LEVELS else "unclear"
    fit = max(0.0, min(1.0, float(data["new_grad_fit"])))
    years = int(data["years_stated"])
    score = max(0, min(10, int(data["score"])))
    return {
        "level": level,
        "new_grad_fit": fit,
        "years_stated": None if years < 0 else years,
        "score": score,
        "reason": str(data["reason"]).strip()[:200],
    }


async def score_posting(client, p: Posting, profile: dict = PROFILE) -> Optional[dict]:
    """Two attempts. Returns None on repeated failure; the caller surfaces the posting as unscored."""
    for attempt in range(2):
        try:
            resp = await client.messages.create(
                model=profile["model"],
                max_tokens=300,
                system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": build_user_message(p, profile["max_description_chars"])}],
                output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
            )
            text = next(b.text for b in resp.content if getattr(b, "type", "") == "text")
            return validate(json.loads(text))
        except (json.JSONDecodeError, StopIteration, ValueError, TypeError, KeyError):
            pass
        except anthropic.APIStatusError as e:
            if e.status_code < 500 and e.status_code != 429:
                return None          # bad request or auth: retrying won't help
        except anthropic.APIConnectionError:
            pass
        if attempt == 0:
            await asyncio.sleep(1)
    return None


async def score_all(client, postings: list[Posting], profile: dict = PROFILE) -> dict[str, Optional[dict]]:
    sem = asyncio.Semaphore(profile["score_concurrency"])

    async def one(p: Posting):
        async with sem:
            return p.key, await score_posting(client, p, profile)

    return dict(await asyncio.gather(*(one(p) for p in postings)))
