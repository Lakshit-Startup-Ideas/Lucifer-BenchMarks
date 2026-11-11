"""Finds the lessons most relevant to a task: plain TF-IDF cosine similarity over words (no model, no download)."""
from __future__ import annotations

import math
import re
from collections import Counter

from .memory import Lesson

_STOP = frozenset("a an the of and or to in is it that this for on with as by be at are was from if its not any each every so then than".split())
_WORD = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 1]


def relevant(query: str, lessons: list[Lesson], k: int = 3, min_score: float = 0.08) -> list[Lesson]:
    if not lessons or k <= 0:
        return []
    docs = [Counter(tokens(l.text)) for l in lessons]
    df: Counter[str] = Counter()
    for d in docs:
        df.update(d.keys())
    n = len(docs)
    idf = {w: math.log((n + 1) / (c + 1)) + 1 for w, c in df.items()}

    def vec(counts: Counter[str]) -> dict[str, float]:
        v = {w: c * idf.get(w, math.log(n + 1) + 1) for w, c in counts.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {w: x / norm for w, x in v.items()}

    q = vec(Counter(tokens(query)))
    scored = []
    for lesson, d in zip(lessons, docs):
        dv = vec(d)
        scored.append((sum(q[w] * dv.get(w, 0.0) for w in q), lesson.version, lesson))
    scored.sort(key=lambda s: (-s[0], -s[1]))
    return [l for score, _, l in scored[:k] if score >= min_score]


def least_relevant(query: str, lessons: list[Lesson], k: int = 3) -> list[Lesson]:
    """The control: the same number of lessons, but the ones that match the task LEAST. With a small memory, random picks are often
    relevant by luck, which would blur the comparison; the least relevant ones add words to the prompt without adding information."""
    if not lessons or k <= 0:
        return []
    ranked = relevant(query, lessons, k=len(lessons), min_score=-1.0)  # all lessons, most relevant first
    return ranked[::-1][:k]
