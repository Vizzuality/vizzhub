"""Generic fuzzy name matcher (stdlib difflib + token Jaccard). No deps."""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

_PARENS = re.compile(r"\(.*?\)")
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize(name: str) -> str:
    value = (name or "").lower()
    value = _PARENS.sub(" ", value)
    value = _YEAR.sub(" ", value)
    value = _NON_ALNUM.sub(" ", value)
    value = re.sub(r"\s+", " ", value).strip()
    if value.endswith(" program"):
        value = value[: -len(" program")].strip()
    return value


def _jaccard(a: str, b: str) -> float:
    sa, sb = set(a.split()), set(b.split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def similarity(a: str, b: str) -> float:
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ratio = SequenceMatcher(None, na, nb).ratio()
    return round(min(1.0, 0.6 * ratio + 0.4 * _jaccard(na, nb)), 4)


@dataclass(frozen=True)
class Scored:
    payload: object
    score: float


def rank(
    query: str,
    candidates: list[tuple[str, object]],
    limit: int = 5,
    threshold: float = 0.35,
) -> list[Scored]:
    scored = [Scored(payload=p, score=similarity(query, name)) for name, p in candidates]
    scored = [s for s in scored if s.score >= threshold]
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[:limit]
