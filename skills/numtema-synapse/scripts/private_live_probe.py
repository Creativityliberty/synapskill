#!/usr/bin/env python3
"""Private-only Ollama E2E probe. Real calls require explicit --execute.

Reports only statuses, counts and timing; never publishes prompts, model output or
private CoR memory. Never reachable through the anonymous MCP HTTP facade.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler

from llm_runtime import OllamaBackend, PrivateAgentRuntime, _NoRedirect, validate_endpoint, load_mission

MODEL_NAME_MAX = 128
MAX_TAGS_BYTES = 128_000
DEFAULT_BLUEPRINT = Path(__file__).resolve().parents[1] / 'examples' / 'blueprint-local-llm.json'


def summarize_workflow(outcome):
    """Fail closed if CoR and Reflexion proof are incomplete."""
    tasks = outcome.get('tasks') if isinstance(outcome, dict) else None
    reviews = outcome.get('reflexion') if isinstance(outcome, dict) else None
    if outcome.get('status') != 'COMPLETED':
        return {'status': 'NO_GO', 'reason': 'workflow_not_completed',
                'workflow_status': outcome.get('status')}
    if not isinstance(tasks, dict) or not tasks or any(t.get('status') != 'COMPLETED' for t in tasks.values()):
        return {'status': 'NO_GO', 'reason': 'task_not_completed'}
    if not isinstance(reviews, dict) or not reviews or not any(
        isinstance(history, list) and history and history[-1].get('status') == 'PASSED'
        for history in reviews.values()
    ):
        return {'status':'NO_GO', 'reason':'missing_passed_reflexion'}
    if type(outcome.get('model_calls')) is not int or outcome['model_calls'] < 2:
        return {'status':'NO_GO','reason':'no_independent_review_call'}
    return {'status':'GO', 'reason':'workflow_and_review_passed',
            'tasks_completed':len(tasks),'model_calls':outcome['model_calls'],
            'reviewed_tasks':sum(1 for hist in reviews.values() if hist and hist[-1].get('status')=='PASSED')}


def _installed_models(url, trusted_hosts, timeout_seconds):
    # Reuse the same strict host validation as the production private worker.
    api_chat = validate_endpoint(url, trusted_hosts=trusted_hosts)
    api_tags = api_chat[:-len('/api/chat')] + '/api/tags'
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    with opener.open(Request(api_tags, method='GET'), timeout=min(timeout_seconds, 30)) as response:
        raw = response.read(MAX_TAGS_BYTES + 1)
        if response.status != 200 or len(raw) > MAX_TAGS_BYTES:
            raise ValueError('Invalid Ollama tags response')
        obj = json.loads(raw)
        if not isinstance(obj, dict) or not isinstance(obj.get('models'), list):
            raise ValueError('Ollama tags response must include models array')
        return sorted(set(item.get('name') or item.get('model') for item in obj['models']
                          if isinstance(item,dict) and isinstance(item.get('name') or item.get('model'),str)))


def probe(model, url, trusted_hosts, execute, timeout_seconds, *, blueprint=None):
    if not execute:
        return {'status':'NOT_EXECUTED','reason':'explicit_execute_required',
                'model_calls':0,'public_http_modified':False}
    if not isinstance(model,str) or not 1 <= len(model) <= MODEL_NAME_MAX:
        raise ValueError('Invalid model name')
    # Reject untrusted remote destinations before any network request.
    validate_endpoint(url, trusted_hosts=trusted_hosts)
    report={'status':'NO_GO','model':model,'public_http_modified':False,
            'checks':{},'model_calls':0}
    started=time.monotonic()
    try:
        names=_installed_models(url,trusted_hosts,timeout_seconds)
        report['checks']['backend_reachable']=True
        report['checks']['model_installed']=model in names
        report['models_installed_count']=len(names)
        if model not in names:
            report['reason']='model_not_installed'
            return report
        backend=OllamaBackend(url,trusted_hosts=trusted_hosts)
        check=backend.complete([
            {'role':'system','content':'Réponds exclusivement par un objet JSON avec probe="synapse".'},
            {'role':'user','content':'Retourne {"probe":"synapse"} en JSON.'}
        ],model=model,max_output_tokens=128,timeout_seconds=timeout_seconds)
        report['checks']['json_mode']=check.get('probe')=='synapse'
        report['model_calls'] += 1
        if not report['checks']['json_mode']:
            report['reason']='json_mode_mismatch'
            return report
        blueprint_path = blueprint or DEFAULT_BLUEPRINT
        payload=json.loads(Path(blueprint_path).read_text(encoding='utf-8'))
        runtime=PrivateAgentRuntime(backend,model=model,max_calls=8,
                                    timeout_seconds=timeout_seconds,max_output_tokens=768,
                                    reflexion=True)
        outcome=runtime.run(payload,execute=True)
        summary=summarize_workflow(outcome)
        report['model_calls']+=outcome.get('model_calls',0)
        report['checks']['cor_reflexion']=summary['status']=='GO'
        report['workflow']=summary
        report['status']=summary['status']
        report['reason']=summary['reason']
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,KeyError,TypeError,RuntimeError) as exc:
        report['status']='NO_GO'
        report['reason']=type(exc).__name__
        report['checks']['runtime_error']=True
    finally:
        report['elapsed_seconds']=round(time.monotonic()-started,3)
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description='Private Ollama live validation (no public API, no secrets)')
    parser.add_argument('--execute',action='store_true',help='Required opt-in for actual Ollama API calls')
    parser.add_argument('--model',default='gemma3:1b')
    parser.add_argument('--url',default='http://127.0.0.1:11434')
    parser.add_argument('--trusted-host',action='append',default=[])
    parser.add_argument('--timeout-seconds',type=int,default=120)
    parser.add_argument('--blueprint',type=Path)
    args=parser.parse_args(argv)
    if not 1<=args.timeout_seconds<=120:
        parser.error('--timeout-seconds must be 1..120')
    try:
        report=probe(args.model,args.url,args.trusted_host,args.execute,args.timeout_seconds,blueprint=args.blueprint)
    except ValueError as exc:
        report={'status':'NO_GO','reason':str(exc)[:160],'model_calls':0,'public_http_modified':False}
    print(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2))
    return 0 if report['status']=='GO' else 2


if __name__=='__main__':
    sys.exit(main())
