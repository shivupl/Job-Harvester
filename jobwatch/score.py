"""Claude scoring with structured outputs. One call per prefilter survivor."""
from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

import anthropic
import openai

from .models import Posting
from .profile import PROFILE

LEVELS = ["new_grad", "junior", "mid", "senior", "unclear"]
CATEGORIES = ["fde", "product", "applied_ai", "devrel", "swe", "other"]
LOCATION_FITS = ["bay_area", "us_remote", "other_us", "non_us", "unknown"]

SCHEMA = {
    "type": "object",
    "properties": {
        "level": {"type": "string", "enum": LEVELS},
        "category": {"type": "string", "enum": CATEGORIES},
        "location_fit": {"type": "string", "enum": LOCATION_FITS},
        "years_stated": {"type": "integer"},
        "fit": {"type": "integer"},
        "relevance": {"type": "integer"},
        "reason": {"type": "string"},
        "comp": {"type": "string"},
    },
    "required": ["level", "category", "location_fit", "years_stated", "fit", "relevance", "reason", "comp"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = f"""You screen job postings for one specific candidate and return strict JSON.

Candidate: {PROFILE["candidate"]}

Read the whole posting. Titles lie; the body tells you the real level and the real work. Return:

- level: the seniority the posting actually wants. "new_grad" if it explicitly welcomes new grads or 0-1 years. "junior" for 1-2 years or an early-career framing. "mid" when responsibilities or requirements imply 3-5 years even if the title is neutral. "senior" for 5+ years, ownership of teams or systems, mentoring. "unclear" only when the body gives no signal.
- category: what the job is, by the work described, not the title.
  "fde" = forward deployed, solutions, implementation, technical success, customer engineer, sales engineer: customer-facing roles that build.
  "product" = associate product manager, product manager, deployment strategist, product operations, chief-of-staff-style builder roles.
  "applied_ai" = applied AI / ML engineer, AI engineer, LLM/agent builder, ML platform.
  "devrel" = developer relations, developer advocate, developer education.
  "swe" = traditional software engineering (frontend, backend, full-stack, infra, platform) with no customer-facing or product framing.
  "other" = anything else that survived.
- location_fit: "bay_area" if the role can be done from the SF Bay Area (on-site, hybrid, or a listed Bay Area office); "us_remote" if remote within the US; "other_us" if a US city outside the Bay Area with no remote option; "non_us" if outside the US only; "unknown" if the posting does not say.
- years_stated: the minimum years of experience the posting states, or -1 if none is stated.
- fit: 0-10, would they realistically hire this candidate.
  9-10: explicitly open to new grads or 0-2 years, requirements match the candidate's background.
  6-8: level not stated or early-career framing; a strong new grad with shipped work could get an interview.
  3-5: reads as mid-level; 3+ years implied by responsibilities; a stretch.
  0-2: senior in substance, or requirements the candidate cannot meet.
  Penalize implied seniority even when the title sounds junior. Ignore location and company fame for fit.
  The candidate has already graduated and can start now. A posting that hires for a start a year or more away (a "2027 new grad" cohort, a summer-2027 class) is a worse fit: take 2 off and say so in the reason. A still-open posting hiring for an immediate start is a plus, not a minus.
- relevance: 0-10, how much this role matches what the candidate wants, judged by the decisive criterion above.
  9-10: writing code and building most days, in a target category, at a startup.
  6-8: mostly building, or a target category with some non-building duties.
  3-5: builder title but the body describes configuration, onboarding, training, account management, or running playbooks; or a category the candidate did not target.
  0-2: not a building role.
  Ignore location for relevance; it is reported separately in location_fit.
- reason: at most 15 words, specific to this posting, no fluff.
- comp: the base salary range the posting states, normalized like "$120K – $160K" (append " + equity" or " + bonus" only if the posting says so; keep the currency if not USD; a single figure like "$150K" is fine). Use the Compensation line if one is given. Empty string if the posting states no pay. Never estimate or infer pay.

Return only the JSON object."""


def build_user_message(p: Posting, max_chars: Optional[int]) -> str:
    desc = p.description
    if max_chars is not None and len(desc) > max_chars:
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
    for k in ("level", "category", "location_fit", "years_stated", "fit", "relevance", "reason"):
        if k not in data:
            raise ValueError(f"missing {k}")
    years = int(data["years_stated"])
    return {
        "level": data["level"] if data["level"] in LEVELS else "unclear",
        "category": data["category"] if data["category"] in CATEGORIES else "other",
        "location_fit": data["location_fit"] if data["location_fit"] in LOCATION_FITS else "unknown",
        "years_stated": None if years < 0 else years,
        "fit": max(0, min(10, int(data["fit"]))),
        "relevance": max(0, min(10, int(data["relevance"]))),
        "reason": str(data["reason"]).strip()[:200],
        "comp": _clean_comp(data.get("comp")),
    }


def _clean_comp(v: Any) -> Optional[str]:
    """LLM-extracted pay range; None unless it names a number."""
    s = " ".join(str(v or "").split())[:80]
    return s if any(ch.isdigit() for ch in s) else None


def make_client(profile: dict = PROFILE):
    """Build the scoring client for PROFILE["provider"]. Keys come from the environment."""
    if profile["provider"] == "openai":
        return openai.AsyncOpenAI()
    if profile["provider"] == "anthropic":
        return anthropic.AsyncAnthropic()
    raise ValueError(f"unknown provider {profile['provider']!r}")


async def _call_anthropic(client, p: Posting, profile: dict) -> str:
    resp = await client.messages.create(
        model=profile["model"],
        max_tokens=300,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": build_user_message(p, profile["max_description_chars"])}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
    )
    return next(b.text for b in resp.content if getattr(b, "type", "") == "text")


async def _call_openai(client, p: Posting, profile: dict) -> str:
    kwargs = {}
    if profile.get("reasoning_effort"):
        kwargs["reasoning_effort"] = profile["reasoning_effort"]
    resp = await client.chat.completions.create(
        model=profile["model"],
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": build_user_message(p, profile["max_description_chars"])}],
        response_format={"type": "json_schema",
                         "json_schema": {"name": "screen", "schema": SCHEMA, "strict": True}},
        max_completion_tokens=profile.get("max_completion_tokens", 2000),
        **kwargs,
    )
    choice = resp.choices[0]
    msg = choice.message
    if getattr(msg, "refusal", None):
        raise ValueError(f"refusal: {msg.refusal}")
    if choice.finish_reason == "length" or not msg.content:
        raise ValueError(f"truncated or empty (finish_reason={choice.finish_reason})")
    return msg.content


_CALLS = {"anthropic": _call_anthropic, "openai": _call_openai}
_AUTH_ERRORS = (anthropic.AuthenticationError, openai.AuthenticationError)
_STATUS_ERRORS = (anthropic.APIStatusError, openai.APIStatusError)
_CONN_ERRORS = (anthropic.APIConnectionError, openai.APIConnectionError)
ATTEMPTS = 3


class ScorerUnavailable(RuntimeError):
    """Every scoring call failed. Raised so the run fails visibly instead of filing everything as unscored."""


def _model_access_flap(e) -> bool:
    """403/404 model_not_found: seen to flap for minutes after a project permission change."""
    code = None
    body = getattr(e, "body", None)
    if isinstance(body, dict):
        code = (body.get("error") or {}).get("code") or body.get("code")
    return e.status_code in (403, 404) and code == "model_not_found"


async def score_posting(client, p: Posting, profile: dict = PROFILE) -> Optional[dict]:
    """Up to ATTEMPTS tries. Returns None on repeated failure; the caller surfaces the posting as unscored."""
    call = _CALLS[profile["provider"]]
    for attempt in range(ATTEMPTS):
        text = None
        try:
            text = await call(client, p, profile)
        except _AUTH_ERRORS:
            raise                    # misconfiguration: fail the run loudly, never mark unscored
        except _STATUS_ERRORS as e:
            if e.status_code < 500 and e.status_code != 429 and not _model_access_flap(e):
                return None          # genuine bad request: retrying won't help
        except _CONN_ERRORS:
            pass
        except (ValueError, StopIteration, KeyError, TypeError, IndexError):
            pass                     # refusal, truncation, or shape mismatch: retry
        if text is not None:
            try:
                return validate(json.loads(text))
            except (json.JSONDecodeError, ValueError, TypeError, KeyError):
                pass                 # malformed output: retry
        if attempt < ATTEMPTS - 1:
            await asyncio.sleep(2 * (attempt + 1))
    return None


async def score_all(client, postings: list[Posting], profile: dict = PROFILE) -> dict[str, Optional[dict]]:
    sem = asyncio.Semaphore(profile["score_concurrency"])

    async def one(p: Posting):
        async with sem:
            return p.key, await score_posting(client, p, profile)

    results = dict(await asyncio.gather(*(one(p) for p in postings)))
    if len(postings) >= 5 and all(v is None for v in results.values()):
        raise ScorerUnavailable(
            f"all {len(postings)} scoring calls failed on {profile['provider']}:{profile['model']}")
    return results
