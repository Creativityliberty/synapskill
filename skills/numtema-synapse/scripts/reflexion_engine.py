#!/usr/bin/env python3
"""Private Reflexion v0.7: deterministic gates plus fallible model review.

A positive model verdict is a *heuristic*, never proof that claims are true.
No network, persistence, tool registration, privileges, or public API surface here.
"""
from __future__ import annotations

import hashlib
import json

MAX_REVIEW_ITEMS = 12
MAX_ITEM_CHARS = 500


class ReflexionVerdictError(ValueError):
    """The review cannot be trusted as a well-typed verdict."""


class ReflexionRejected(ValueError):
    """A valid review denied acceptance and requests bounded correction."""


def validate_verdict(verdict):
    """Fail closed on missing, malformed or self-contradictory reviewer outputs."""
    if not isinstance(verdict, dict) or set(verdict) != {'passed', 'issues', 'suggestions'}:
        raise ReflexionVerdictError('Reviewer must return passed, issues, suggestions only')
    if type(verdict['passed']) is not bool:
        raise ReflexionVerdictError('Reviewer passed must be boolean')
    for field in ('issues', 'suggestions'):
        arr = verdict[field]
        if (not isinstance(arr, list) or len(arr) > MAX_REVIEW_ITEMS or
            any(not isinstance(v, str) or not v.strip() or len(v) > MAX_ITEM_CHARS for v in arr)):
            raise ReflexionVerdictError('Reviewer '+field+' must be bounded nonempty strings')
    if verdict['passed'] and verdict['issues']:
        raise ReflexionVerdictError('Passing review must not declare issues')
    if not verdict['passed'] and not verdict['issues']:
        raise ReflexionVerdictError('Rejected review requires actionable issues')
    return {'passed': verdict['passed'], 'issues':list(verdict['issues']),
            'suggestions':list(verdict['suggestions'])}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
                                  separators=(',',':'),default=str).encode('utf-8')).hexdigest()


def redacted_receipt(*, attempt, status, candidate, issues, suggestions=(), reviewer_model=None):
    """Keep only hashes and issue descriptions, not the complete generated text."""
    return {'attempt': attempt, 'status':status, 'candidate_sha256':fingerprint(candidate),
            'issues': list(issues)[:MAX_REVIEW_ITEMS],
            'suggestions': list(suggestions)[:MAX_REVIEW_ITEMS],
            'reviewer_model': reviewer_model}
