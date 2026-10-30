#!/usr/bin/env python3
"""Operator-only CLI for explicit Cognitive Memory approval and deletion.

Do NOT expose this CLI through public MCP tools, HTTP routes, browser JS or workflow inputs.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from cognitive_memory import CognitiveMemory


def main(argv=None):
    ap=argparse.ArgumentParser(description='Synapse private, opt-in cognitive memory (operator only)')
    ap.add_argument('--db',required=True,type=Path,help='Private SQLite DB path outside public serving directory')
    sub=ap.add_subparsers(dest='action',required=True)
    add=sub.add_parser('approve',help='Save a human-reviewed Reflexion lesson')
    add.add_argument('--report',required=True,type=Path)
    add.add_argument('--task-id',required=True)
    add.add_argument('--scope',required=True)
    add.add_argument('--insight',required=True)
    add.add_argument('--retention-days',type=int,default=30)
    add.add_argument('--operator-reviewed',action='store_true')
    recall=sub.add_parser('recall',help='Recall only exact project scope')
    recall.add_argument('--scope',required=True)
    recall.add_argument('--limit',type=int,default=5)
    purge=sub.add_parser('purge-scope',help='Delete all lessons in an exact scope')
    purge.add_argument('--scope',required=True)
    purge.add_argument('--confirm',action='store_true')
    delete=sub.add_parser('delete',help='Delete one lesson')
    delete.add_argument('--scope',required=True)
    delete.add_argument('--id',required=True)
    delete.add_argument('--confirm',action='store_true')
    exp=sub.add_parser('purge-expired',help='Delete expired lessons')
    exp.add_argument('--confirm',action='store_true')
    a=ap.parse_args(argv)
    try:
        if a.action in ('purge-scope','delete','purge-expired') and not a.confirm:
            raise PermissionError('Destructive command requires --confirm')
        if a.action=='approve' and not a.operator_reviewed:
            raise PermissionError('Approval requires --operator-reviewed from a trusted operator')
        if a.action != 'approve' and not a.db.exists():
            raise FileNotFoundError('No configured private memory database')
        store=CognitiveMemory(a.db,create=(a.action != 'recall'))
        if a.action=='approve':
            report=json.loads(a.report.read_text(encoding='utf-8'))
            result={'id':store.approve(a.scope,a.insight,report,a.task_id,
                                      operator_reviewed=True,retention_days=a.retention_days),
                    'status':'APPROVED'}
        elif a.action=='recall':result={'lessons':store.recall(a.scope,limit=a.limit)}
        elif a.action=='purge-scope':result={'deleted':store.purge_scope(a.scope)}
        elif a.action=='delete':result={'deleted':store.delete(a.scope,a.id)}
        else:result={'deleted':store.purge_expired()}
        print(json.dumps(result,ensure_ascii=False,sort_keys=True))
        return 0
    except (OSError,ValueError,PermissionError,KeyError,json.JSONDecodeError) as exc:
        print(f'Synapse private cognitive memory blocked: {exc}',file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
