#!/usr/bin/env python3
"""Nümtema Agent Forge v0.2 - bounded, auditable, local CoR/DAG runner.

No LLM, network, shell, or ChatGPT connector is started by this file.
A trusted host may register real callable tools, with permissions and grants.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Callable

from validate_payload import validate_contract

SENSITIVE = {'external_write', 'deployment', 'financial_spend'}
ALL_CAPABILITIES = {'read', 'draft', *SENSITIVE}
MAX_TASKS = 64
MAX_BYTES = 2_000_000


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), default=str)


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def local_echo(params, upstream, feedback):
    return {'message': str(params.get('message', '')), 'upstream': list(upstream)}


def local_extract_fields(params, upstream, feedback):
    data = params.get('data', {})
    fields = params.get('fields', [])
    if not isinstance(data, dict) or not isinstance(fields, list):
        raise ValueError('data must be object and fields must be list')
    missing = [x for x in fields if x not in data]
    if missing:
        raise ValueError('Missing fields: ' + ', '.join(map(str, missing)))
    return {str(key): data[key] for key in fields}


def local_render_template(params, upstream, feedback):
    template = params.get('template')
    if not isinstance(template, str):
        raise ValueError('template must be string')
    values = dict(params.get('values') or {})
    from_task = params.get('values_from_task')
    if from_task:
        data = upstream.get(from_task, {})
        if not isinstance(data, dict):
            raise ValueError('upstream values must be object')
        values.update(data)

    def replace(match):
        key = match.group(1)
        if key not in values:
            raise ValueError('Template key missing: ' + key)
        return str(values[key])

    text = re.sub(r'\{\{([a-zA-Z0-9_\-]+)\}\}', replace, template)
    return {'text': text}


def local_assert_contains(params, upstream, feedback):
    text = params.get('text')
    source = params.get('source_task')
    if source:
        if source not in upstream:
            raise ValueError('Unknown source task: ' + source)
        output = upstream[source]
        text = output.get('text', '') if isinstance(output, dict) else str(output)
    if not isinstance(text, str):
        raise ValueError('text must be string')
    fragments = params.get('fragments', [])
    if not isinstance(fragments, list) or any(not isinstance(f, str) for f in fragments):
        raise ValueError('fragments must be strings')
    missing = [f for f in fragments if f not in text]
    return {'passed': not missing, 'missing': missing,
            'evidence': [{'check': 'contains', 'fragment': f, 'passed': f not in missing} for f in fragments]}


class LessonMemory:
    """Persistent lessons only when the caller opts into a DB and approves each write."""
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS lessons (
                id TEXT PRIMARY KEY, scope TEXT NOT NULL, insight TEXT NOT NULL,
                evidence TEXT NOT NULL, created_at TEXT NOT NULL)''')

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def remember(self, scope: str, insight: str, evidence: list, *, approved=False):
        if not approved:
            raise PermissionError('Persistent lesson requires explicit trusted-host approval')
        if not scope or not insight or not evidence or not isinstance(evidence, list):
            raise ValueError('Lesson requires scope, insight and supporting evidence')
        key = digest({'scope': scope, 'insight': insight, 'evidence': evidence})
        with self._connect() as db:
            db.execute('INSERT OR IGNORE INTO lessons VALUES (?, ?, ?, ?, ?)',
                       (key, scope, insight, canonical(evidence), now()))
        return key

    def recall(self, scope: str, *, limit=10):
        with self._connect() as db:
            rows = db.execute(
                'SELECT id, scope, insight, evidence, created_at FROM lessons WHERE scope=? ORDER BY created_at DESC LIMIT ?',
                (scope, max(0, min(limit, 50)))).fetchall()
        return [{'id': r[0], 'scope': r[1], 'insight': r[2],
                 'evidence': json.loads(r[3]), 'created_at': r[4]} for r in rows]


class ForgeRuntime:
    """Execute a small DAG of trusted tool adapters with CoR validation.

    `grants` MUST come from the host approval subsystem, never from mission JSON.
    """
    def __init__(self, *, state_db: str | Path | None = None, grants=None):
        self.registry: dict[str, dict] = {}
        self.state_db = Path(state_db) if state_db is not None else None
        self.grants = frozenset(grants or ())
        self.register('local.echo', local_echo, capability='draft')
        self.register('local.extract_fields', local_extract_fields, capability='read')
        self.register('local.render_template', local_render_template, capability='draft')
        self.register('local.assert_contains', local_assert_contains, capability='read')
        if self.state_db:
            self.state_db.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as db:
                db.execute('''CREATE TABLE IF NOT EXISTS receipts (
                    mission_id TEXT, task_id TEXT, fingerprint TEXT, result TEXT,
                    created_at TEXT, PRIMARY KEY (mission_id, task_id, fingerprint))''')
                db.execute('''CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, mission_id TEXT, task_id TEXT,
                    event_type TEXT, details TEXT, created_at TEXT)''')

    def _connect(self):
        return sqlite3.connect(self.state_db)

    def register(self, name: str, handler: Callable, *, capability='draft', version='1'):
        if capability not in ALL_CAPABILITIES:
            raise ValueError('Unknown capability: ' + capability)
        if not callable(handler) or not name or not isinstance(name, str):
            raise ValueError('Provide a named callable')
        self.registry[name] = {'handler': handler, 'capability': capability, 'version': version}

    def _event(self, mid, tid, name, details):
        if self.state_db is None:
            return
        with self._connect() as db:
            db.execute('INSERT INTO events(mission_id,task_id,event_type,details,created_at) VALUES (?,?,?,?,?)',
                       (mid, tid, name, canonical(details), now()))

    def _get_cached(self, mid, tid, fingerprint):
        if not self.state_db:
            return None
        with self._connect() as db:
            row = db.execute('SELECT result FROM receipts WHERE mission_id=? AND task_id=? AND fingerprint=?',
                             (mid,tid,fingerprint)).fetchone()
        return json.loads(row[0]) if row else None

    def _cache(self, mid, tid, fingerprint, result):
        if not self.state_db:
            return
        with self._connect() as db:
            db.execute('INSERT OR REPLACE INTO receipts VALUES (?,?,?,?,?)',
                       (mid,tid,fingerprint,canonical(result),now()))

    def _preflight(self, spec):
        issues = []
        if not isinstance(spec, dict):
            return [], ['Mission must be a JSON object']
        mid = spec.get('mission_id')
        if not isinstance(mid, str) or not mid.strip():
            issues.append('mission_id: required')
        tasks = spec.get('tasks')
        if not isinstance(tasks, list) or not tasks or len(tasks) > MAX_TASKS:
            return [], issues + [f'tasks: list of 1..{MAX_TASKS} required']
        mapping = {}
        for task in tasks:
            if not isinstance(task, dict):
                issues.append('task must be object')
                continue
            tid = task.get('id')
            if not isinstance(tid,str) or not tid or tid in mapping:
                issues.append(f'task id missing/duplicate: {tid!r}')
                continue
            mapping[tid] = task
            contract = task.get('contract')
            issues.extend(f'{tid}: {i}' for i in validate_contract(contract))
            tool = task.get('tool')
            if tool not in self.registry:
                issues.append(f'{tid}: tool {tool!r} is not registered in the trusted host')
            if isinstance(contract, dict):
                if tool not in (contract.get('tools') or {}).get('allowlist', []):
                    issues.append(f'{tid}: tool {tool!r} not in CoR allowlist')
                if (contract.get('permissions') or {}).get('requested_tools') and tool not in contract['permissions']['requested_tools']:
                    issues.append(f'{tid}: tool not requested in CoR permissions')
            deps = task.get('depends_on', [])
            if not isinstance(deps,list) or not all(isinstance(x,str) for x in deps):
                issues.append(f'{tid}: depends_on must be array of strings')
            if not isinstance(task.get('params', {}), dict):
                issues.append(f'{tid}: params must be object')
            checks=task.get('checks', {})
            if not isinstance(checks,dict):
                issues.append(f'{tid}: checks must be object')
            else:
                for field in ('required_keys','required_text'):
                    value=checks.get(field,[])
                    if not isinstance(value,list) or any(not isinstance(x,str) for x in value):
                        issues.append(f'{tid}: checks.{field} must be list of strings')
                if 'require_passed' in checks and type(checks['require_passed']) is not bool:
                    issues.append(f'{tid}: checks.require_passed must be boolean')
        for tid, task in mapping.items():
            for dep in task.get('depends_on', []) if isinstance(task.get('depends_on',[]),list) else []:
                if dep not in mapping:
                    issues.append(f'{tid}: unknown dependency {dep!r}')
                if dep == tid:
                    issues.append(f'{tid}: cycle through itself')
        if issues:
            return [], issues
        order = []
        remaining = set(mapping)
        while remaining:
            ready = [tid for tid in mapping if tid in remaining and
                     all(dep in order for dep in mapping[tid].get('depends_on', []))]
            if not ready:
                return [], ['cycle detected in dependency DAG']
            order.extend(ready)
            remaining -= set(ready)
        return order, []

    def _permission_issue(self, mid, task):
        tool_id = task['tool']
        capability = self.registry[tool_id]['capability']
        permissions = task['contract'].get('permissions', {})
        if capability in ('read', 'draft') and permissions.get(capability) is False:
            return f'{capability}: prohibited by CoR'
        if capability in SENSITIVE:
            approvals = permissions.get('require_approval') or []
            if capability not in approvals:
                return f'{capability}: approval requirement missing in CoR'
            grant = f'{mid}:{task["id"]}:{tool_id}'
            if grant not in self.grants:
                return f'{capability}: trusted-host approval missing for {grant}'
        return None

    @staticmethod
    def _check(result, checks):
        issues = []
        if not isinstance(result, dict):
            return ['Tool output must be an object']
        for key in checks.get('required_keys', []):
            if key not in result:
                issues.append('required output key missing: ' + str(key))
        if checks.get('require_passed') and result.get('passed') is not True:
            issues.append('quality gate did not pass: ' + ', '.join(map(str, result.get('missing', []))))
        for needle in checks.get('required_text', []):
            if needle not in canonical(result):
                issues.append('required text missing: ' + str(needle))
        return issues

    def run(self, spec, *, execute=False):
        order, issues = self._preflight(spec)
        mid = spec.get('mission_id','unknown') if isinstance(spec,dict) else 'unknown'
        if issues:
            return {'mission_id': mid, 'status': 'BLOCKED', 'issues': issues, 'tasks': {}}
        if not execute:
            return {'mission_id': mid, 'status': 'PLANNED', 'order': order,
                    'tasks': {tid: {'tool': next(t for t in spec['tasks'] if t['id']==tid)['tool']} for tid in order},
                    'issues': []}
        mapping = {t['id']: t for t in spec['tasks']}
        outputs = {}
        results = {}
        for tid in order:
            t = mapping[tid]
            deps = t.get('depends_on',[])
            bad = [dep for dep in deps if results[dep]['status'] != 'COMPLETED']
            if bad:
                results[tid] = {'status': 'BLOCKED', 'issues': ['upstream task not completed: '+', '.join(bad)], 'attempts': 0}
                self._event(mid,tid,'BLOCKED', results[tid]['issues'])
                continue
            issue = self._permission_issue(mid,t)
            if issue:
                results[tid] = {'status':'BLOCKED', 'issues':[issue], 'attempts':0}
                self._event(mid,tid,'BLOCKED', [issue])
                continue
            adapter = self.registry[t['tool']]
            upstream = {dep:outputs[dep] for dep in deps}
            fingerprint = digest({'task':t,'upstream':upstream,'tool_version':adapter['version'], 'capability':adapter['capability']})
            if adapter['capability'] not in SENSITIVE:
                cached = self._get_cached(mid,tid,fingerprint)
            else:
                cached = None
            if cached is not None and not self._check(cached['output'], t.get('checks',{})):
                results[tid] = {**cached, 'cached':True}
                outputs[tid] = cached['output']
                self._event(mid,tid,'CACHE_HIT', {'fingerprint':fingerprint})
                continue
            # Side-effecting operations are never automatically retried: duplicate writes/spend risk.
            max_attempts = (1 if adapter['capability'] in SENSITIVE else
                            1 + t['contract']['reflection']['max_revisions'])
            feedback = []
            for attempt in range(1,max_attempts+1):
                try:
                    output=adapter['handler'](t.get('params',{}),upstream,list(feedback))
                    if len(canonical(output).encode('utf-8')) > MAX_BYTES:
                        raise ValueError('Tool output exceeds maximum size')
                    check_issues = self._check(output,t.get('checks',{}))
                except Exception as exc:
                    output = None
                    check_issues = ([f'tool error ({type(exc).__name__}); see trusted host logs']
                                    if adapter['capability'] in SENSITIVE else
                                    [f'tool error ({type(exc).__name__}): {exc}'])
                self._event(mid,tid,'ATTEMPT',{'attempt':attempt,'issues':check_issues})
                if not check_issues:
                    receipt = {'contract_id':t['contract']['contract_id'], 'status':'COMPLETED',
                               'deliverables': output, 'output':output, 'evidence':[{'check':'task_checks','passed':True}], 'issues':[],
                               'attempts':attempt, 'cached':False,
                               'validation': {'mandatory_passed':True,
                                              'evidence':[{'check':'task_checks','passed':True}]}}
                    results[tid]=receipt
                    outputs[tid]=output
                    if adapter['capability'] not in SENSITIVE:
                        self._cache(mid,tid,fingerprint,receipt)
                    break
                feedback.append({'attempt':attempt,'issues':check_issues})
            else:
                results[tid]={'status':'FAILED','issues':check_issues,'feedback':feedback,
                              'attempts':max_attempts,'cached':False}
        statuses = [r['status'] for r in results.values()]
        status = 'BLOCKED' if 'BLOCKED' in statuses else ('FAILED' if 'FAILED' in statuses else 'COMPLETED')
        return {'mission_id':mid,'status':status,'order':order,'tasks':results,
                'validation': {'all_tasks_completed':status=='COMPLETED'},
                'issues': [f'{key}: {e}' for key,r in results.items() for e in r.get('issues',[])]}


def main():
    ap=argparse.ArgumentParser(description='Nümtema Synapse Agent Forge local DAG engine')
    ap.add_argument('mission',type=Path, help='JSON file with mission_id and CoR tasks')
    ap.add_argument('--execute',action='store_true',help='Run registered local tools (default: dry-run plan)')
    ap.add_argument('--state-db',type=Path,help='Opt in to persistent SQLite receipts/events')
    args=ap.parse_args()
    mission=json.loads(args.mission.read_text(encoding='utf-8'))
    report=ForgeRuntime(state_db=args.state_db).run(mission,execute=args.execute)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report['status'] in ('COMPLETED','PLANNED') else 2


if __name__=='__main__':
    raise SystemExit(main())
