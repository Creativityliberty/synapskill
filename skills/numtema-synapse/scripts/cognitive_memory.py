#!/usr/bin/env python3
"""Synapse v0.8 Cognitive Memory: opt-in, operator-reviewed, scoped private lessons.

Never imported or initialized by public_mcp_policy/mcp_http_server.
Successful LLM review is heuristic, not verified factual truth. No automatic writes.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from reflexion_engine import fingerprint

SCOPE_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$')
MAX_INSIGHT_CHARS = 600
MAX_RECALL = 8
MAX_RETENTION = 365


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


class CognitiveMemory:
    """Private SQLite store. The host must explicitly create and approve each lesson."""

    def __init__(self, db_path, *, create=False, clock=None):
        self.db_path = Path(db_path).expanduser()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.read_only = not create
        if self.db_path.is_symlink():
            raise ValueError('Refusing symlink memory database')
        if not self.db_path.exists():
            if not create:
                raise FileNotFoundError('Cognitive memory is not configured; no DB was created')
            self.db_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if os.name == 'posix':
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
                if hasattr(os, 'O_NOFOLLOW'):flags |= os.O_NOFOLLOW
                fd = os.open(str(self.db_path), flags, 0o600)
                os.close(fd)
            else:
                self.db_path.touch(exist_ok=False)
        if not self.db_path.is_file() or self.db_path.is_symlink():
            raise ValueError('Memory database must be a regular file')
        if os.name == 'posix' and self.db_path.stat().st_mode & 0o077:
            raise PermissionError('Private SQLite database permissions must be owner-only (0600)')
        with self._connect() as db:
            if self.read_only:
                found = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='approved_lessons'").fetchone()
                if found is None:
                    raise ValueError('No approved cognitive lessons table in selected read-only database')
                return
            db.execute('''CREATE TABLE IF NOT EXISTS approved_lessons (
                id TEXT PRIMARY KEY, scope TEXT NOT NULL, insight TEXT NOT NULL,
                evidence TEXT NOT NULL, approved_at TEXT NOT NULL,
                expires_at TEXT NOT NULL, provenance TEXT NOT NULL DEFAULT 'operator_reviewed_reflexion')''')
            db.execute('CREATE INDEX IF NOT EXISTS idx_approved_lessons_scope ON approved_lessons(scope,expires_at)')

    def _connect(self):
        if self.read_only:
            return sqlite3.connect(self.db_path.absolute().as_uri()+'?mode=ro', uri=True, timeout=5)
        return sqlite3.connect(str(self.db_path), timeout=5)

    def _require_write(self):
        if self.read_only:
            raise PermissionError('Memory store opened read-only; private worker cannot modify lessons')

    def _now(self):
        dt = self.clock()
        if not isinstance(dt, datetime) or dt.tzinfo is None:
            raise ValueError('Clock must return timezone-aware datetime')
        return dt.astimezone(timezone.utc)

    @staticmethod
    def _scope(scope):
        if not isinstance(scope,str) or not SCOPE_PATTERN.fullmatch(scope):
            raise ValueError('Scope must be a nonempty explicit project key [a-zA-Z0-9._:/-], <=128 chars')
        return scope

    def approve(self, scope, insight, report, task_id, *, operator_reviewed=False, retention_days=30):
        """Write ONLY after a separate human approves a COMPLETED reflexion receipt.

        The source report is still untrusted; operator review is required. No background auto-learn.
        """
        self._require_write()
        if operator_reviewed is not True:
            raise PermissionError('Operator review is required for each persistent lesson')
        scope = self._scope(scope)
        if not isinstance(insight,str) or not insight.strip() or len(insight)>MAX_INSIGHT_CHARS:
            raise ValueError('Insight must be a reviewed concise string (1..600 chars)')
        if type(retention_days) is not int or not 1<=retention_days<=MAX_RETENTION:
            raise ValueError('retention_days must be 1..365')
        if not isinstance(report,dict) or report.get('status')!='COMPLETED':
            raise ValueError('Only a completed mission report is eligible')
        if not isinstance(task_id,str) or not task_id.strip():
            raise ValueError('Task ID is required')
        task = (report.get('tasks') or {}).get(task_id)
        if not isinstance(task,dict) or task.get('status')!='COMPLETED' or not isinstance(task.get('output'),dict):
            raise ValueError('Task must have completed with a structured output')
        if (task.get('validation') or {}).get('mandatory_passed') is not True:
            raise ValueError('Deterministic CoR validation must pass')
        reviews=(report.get('reflexion') or {}).get(task_id)
        if not isinstance(reviews,list) or not reviews or not isinstance(reviews[-1],dict):
            raise ValueError('A final Reflexion review is required')
        receipt=reviews[-1]
        if receipt.get('status')!='PASSED' or receipt.get('issues') != []:
            raise ValueError('Final Reflexion review did not pass')
        sha=fingerprint(task['output'])
        if receipt.get('candidate_sha256') != sha:
            raise ValueError('Reflexion fingerprint does not match approved candidate')
        mission_id=report.get('mission_id')
        if not isinstance(mission_id,str) or not mission_id.strip() or len(mission_id)>128:
            raise ValueError('Invalid mission ID')
        evidence={'mission_id':mission_id, 'task_id':task_id,
                  'candidate_sha256':sha, 'reviewer_model':receipt.get('reviewer_model')}
        key=hashlib.sha256(_json({'scope':scope,'insight':insight.strip(),'evidence':evidence}).encode()).hexdigest()
        at=self._now()
        with self._connect() as db:
            db.execute('''INSERT OR IGNORE INTO approved_lessons
                (id,scope,insight,evidence,approved_at,expires_at,provenance)
                VALUES (?,?,?,?,?,?,?)''',
                (key,scope,insight.strip(),_json(evidence),at.isoformat(),
                 (at+timedelta(days=retention_days)).isoformat(), 'operator_reviewed_reflexion'))
        return key

    def recall(self, scope, *, limit=5):
        scope=self._scope(scope)
        if type(limit) is not int or not 1<=limit<=MAX_RECALL:
            raise ValueError('Recall limit must be 1..8')
        with self._connect() as db:
            rows=db.execute('''SELECT id,scope,insight,evidence,approved_at,expires_at,provenance
                FROM approved_lessons WHERE scope=? AND expires_at>?
                ORDER BY approved_at DESC,id DESC LIMIT ?''',
                (scope,self._now().isoformat(),limit)).fetchall()
        return [{'id':r[0],'scope':r[1],'insight':r[2],'evidence':json.loads(r[3]),
                 'approved_at':r[4],'expires_at':r[5],'provenance':r[6]} for r in rows]

    def delete(self, scope, lesson_id):
        self._require_write()
        scope=self._scope(scope)
        if not isinstance(lesson_id,str) or not re.fullmatch(r'[0-9a-f]{64}',lesson_id):
            raise ValueError('Lesson ID must be SHA-256 hex')
        with self._connect() as db:
            cur=db.execute('DELETE FROM approved_lessons WHERE scope=? AND id=?',(scope,lesson_id))
            return bool(cur.rowcount)

    def purge_scope(self,scope):
        self._require_write()
        scope=self._scope(scope)
        with self._connect() as db:
            return db.execute('DELETE FROM approved_lessons WHERE scope=?',(scope,)).rowcount

    def purge_expired(self):
        self._require_write()
        with self._connect() as db:
            return db.execute('DELETE FROM approved_lessons WHERE expires_at<=?',(self._now().isoformat(),)).rowcount
