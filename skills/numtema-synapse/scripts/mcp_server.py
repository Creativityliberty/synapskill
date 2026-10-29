#!/usr/bin/env python3
"""Nümtema Synapse MCP stdio server (self-contained, offline, safe by default).

Supports MCP 2026-07-28 per-request metadata and legacy 2025 handshake.
No external tools, network connectors, LLM calls, shell or spending are registered.
A ChatGPT plugin containing this file does NOT automatically run this process.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import deque
from pathlib import Path

from agent_forge import AgentForge
from forge_runtime import ForgeRuntime, LessonMemory
from validate_payload import validate_contract

SERVER_NAME = 'numtema-synapse-cognitive-os'
SERVER_VERSION = '0.3.0'
MODERN_VERSION = '2026-07-28'
LEGACY_VERSIONS = ('2025-11-25', '2025-06-18', '2025-03-26')
SUPPORTED_VERSIONS = (MODERN_VERSION,) + LEGACY_VERSIONS
MAX_MESSAGE_BYTES = 1_000_000
MAX_RESULT_BYTES = 1_000_000
META_VERSION = 'io.modelcontextprotocol/protocolVersion'
META_CLIENT = 'io.modelcontextprotocol/clientInfo'
META_CAPS = 'io.modelcontextprotocol/clientCapabilities'

AGENTS = [
    ('FocusAgent', 'Clarification du mandat'), ('Mapper', 'Cartographie des systèmes'),
    ('Morphius', 'Transformations et représentations'),
    ('ExplorerAgent', 'Variantes et scénarios'), ('Imagino', 'Concepts créatifs'),
    ('Rhetorica', 'Argumentaire et rédaction'), ('Planner', 'Dépendances et plan'),
    ('FlowMaintainer', 'Suivi de mission'), ('ResearchAgent', 'Recherche et provenance'),
    ('CodeAgent', 'Code et tests'), ('VerifierAgent', 'Critères vérifiables'),
    ('EthicsGuardian', 'Risques et autorisations'),
    ('IntegratorAgent', 'Synthèse des livrables'), ('PublisherAgent', 'Diffusion autorisée'),
    ('PersonaAdapter', 'Ton et format'), ('PostMortemAgent', 'Retours et corrections'),
    ('NümtemaAgent', 'Adaptation de mission'), ('Synapse', 'Orchestration')
]


def obj_schema(properties=None, required=()):
    return {'type': 'object', 'properties': properties or {}, 'required': list(required),
            'additionalProperties': False}


def object_arg(description):
    return {'type': 'object', 'description': description}


def text_arg(description):
    return {'type': 'string', 'description': description}


TOOLS = [
    {'name':'numtema.list_agents', 'title':'Nümtema Agent Registry',
     'description':'Liste les profils agents Nümtema (rôles conceptuels, non sous-processus LLM).',
     'inputSchema':obj_schema(), 'annotations':{'readOnlyHint':True}},
    {'name':'numtema.validate_cor', 'title':'Validation de contrat CoR',
     'description':'Vérifie la structure d’un contrat CoR 2.0, sans exécuter ni attribuer de permission.',
     'inputSchema':obj_schema({'contract':object_arg('Contrat CoR 2.0')},['contract']),
     'annotations':{'readOnlyHint':True}},
    {'name':'numtema.compile_blueprint', 'title':'Agent Forge — Compile',
     'description':'Transforme un blueprint en mission DAG avec contrats CoR; aucune exécution.',
     'inputSchema':obj_schema({'blueprint':object_arg('Blueprint Agent Forge')},['blueprint']),
     'annotations':{'readOnlyHint':True}},
    {'name':'numtema.plan_workflow', 'title':'Synapse — Plan',
     'description':'Valide les dépendances et retourne l’ordre DAG sans exécuter les tâches.',
     'inputSchema':obj_schema({'mission':object_arg('Mission compilée')},['mission']),
     'annotations':{'readOnlyHint':True}},
    {'name':'numtema.execute_workflow', 'title':'Synapse — Exécution locale',
     'description':'Exécute uniquement des adaptateurs locaux read/draft si le processus a été démarré avec --allow-execute. Aucune fonction réseau, paiement ou publication.',
     'inputSchema':obj_schema({'mission':object_arg('Mission compilée')},['mission']),
     'annotations':{'readOnlyHint':False, 'destructiveHint':False, 'openWorldHint':False}},
    {'name':'numtema.recall_lessons', 'title':'Reflexion — Leçons locales',
     'description':'Lecture de leçons SQLite locales uniquement si --lessons-db a été fourni. Aucune écriture distante.',
     'inputSchema':obj_schema({'scope':text_arg('Périmètre exact des leçons'), 'limit':{'type':'integer','minimum':1,'maximum':30}},['scope']),
     'annotations':{'readOnlyHint':True}},
]
TOOLS.sort(key=lambda item: item['name'])
TOOL_NAMES = {t['name'] for t in TOOLS}


def rpc_error(request_id, code, message, data=None):
    payload={'jsonrpc':'2.0','id':request_id,'error':{'code':code,'message':message}}
    if data is not None:
        payload['error']['data']=data
    return payload


def tool_result(data, *, failed=False, modern=True):
    if not isinstance(data, dict):
        data={'value':data}
    serialized=json.dumps(data,sort_keys=True,ensure_ascii=False,separators=(',',':'))
    if len(serialized.encode('utf-8')) > MAX_RESULT_BYTES:
        return tool_result({'error':'Result exceeds maximum size'},failed=True,modern=modern)
    result={'content':[{'type':'text','text':serialized}], 'structuredContent':data,'isError':bool(failed)}
    if modern:
        result={'resultType':'complete',**result}
    return result


class SynapseMCPServer:
    def __init__(self, *, allow_execute=False, state_db=None, lessons_db=None, max_calls_per_minute=100):
        self.allow_execute=bool(allow_execute)
        self.runtime=ForgeRuntime(state_db=state_db, grants=())
        self.lessons=LessonMemory(lessons_db) if lessons_db is not None else None
        self.legacy_initialized=False
        self.max_calls_per_minute=max_calls_per_minute
        self.calls=deque()

    def _rate_limit_ok(self):
        current=time.monotonic()
        while self.calls and current-self.calls[0]>60:
            self.calls.popleft()
        if len(self.calls)>=self.max_calls_per_minute:
            return False
        self.calls.append(current)
        return True

    def call_tool(self, name, args=None, *, modern=True):
        if name not in TOOL_NAMES:
            raise KeyError(name)
        args=args or {}
        if not isinstance(args,dict):
            raise ValueError('arguments must be an object')
        # Do not consume optional grants/permissions from remote arguments.
        if name=='numtema.list_agents':
            data={'agents':[{'agent_id':a,'responsibility':b,'mode':'role_only'} for a,b in AGENTS],
                  'note':'Profiles are not separately running model processes'}
        elif name=='numtema.validate_cor':
            if not isinstance(args.get('contract'),dict):
                raise ValueError('contract must be an object')
            issues=validate_contract(args['contract'])
            data={'valid':not issues,'issues':issues,'scope':'structural_and_policy_only'}
        elif name=='numtema.compile_blueprint':
            if not isinstance(args.get('blueprint'),dict):
                raise ValueError('blueprint must be an object')
            data=AgentForge().compile(args['blueprint'])
        elif name=='numtema.plan_workflow':
            if not isinstance(args.get('mission'),dict):
                raise ValueError('mission must be an object')
            data=self.runtime.run(args['mission'],execute=False)
        elif name=='numtema.execute_workflow':
            if not self.allow_execute:
                return tool_result({'error':'Local execution disabled: restart the trusted host with --allow-execute'},failed=True,modern=modern)
            if not isinstance(args.get('mission'),dict):
                raise ValueError('mission must be an object')
            data=self.runtime.run(args['mission'],execute=True)
        elif name=='numtema.recall_lessons':
            scope=args.get('scope')
            limit=args.get('limit',10)
            if not isinstance(scope,str) or not scope.strip() or len(scope)>256:
                raise ValueError('scope must be a nonempty string <= 256 chars')
            if type(limit) is not int or limit<1 or limit>30:
                raise ValueError('limit must be an integer 1..30')
            data=({'status':'NOT_CONFIGURED','lessons':[]} if self.lessons is None
                  else {'status':'COMPLETED','lessons':self.lessons.recall(scope,limit=limit)})
        else:
            raise KeyError(name)
        return tool_result(data,modern=modern)

    def _require_meta(self, params, request_id):
        meta=params.get('_meta') if isinstance(params,dict) else None
        if not isinstance(meta,dict):
            return rpc_error(request_id,-32602,'Modern MCP requires params._meta')
        version=meta.get(META_VERSION)
        if version not in SUPPORTED_VERSIONS or version!=MODERN_VERSION:
            return rpc_error(request_id,-32022,'Unsupported protocol version',
                             {'supported':list(SUPPORTED_VERSIONS),'requested':version})
        if not isinstance(meta.get(META_CLIENT),dict) or not isinstance(meta.get(META_CAPS),dict):
            return rpc_error(request_id,-32602,'Missing modern MCP clientInfo/clientCapabilities')
        return None

    def handle(self, msg):
        if not isinstance(msg,dict) or msg.get('jsonrpc')!='2.0' or not isinstance(msg.get('method'),str):
            return rpc_error(msg.get('id') if isinstance(msg,dict) else None,-32600,'Invalid JSON-RPC request')
        if 'id' not in msg:
            # Ignore notifications; never produce unsolicited stdout lines.
            return None
        request_id=msg['id']
        if type(request_id) not in (str,int):
            return rpc_error(None,-32600,'Invalid request ID')
        method=msg['method']
        params=msg.get('params',{})
        if not isinstance(params,dict):
            return rpc_error(request_id,-32602,'params must be an object')
        if not self._rate_limit_ok():
            return rpc_error(request_id,-32000,'Rate limit exceeded')

        if method=='initialize':
            if params.get('protocolVersion') not in LEGACY_VERSIONS:
                return rpc_error(request_id,-32022,'Unsupported protocol version',
                                 {'supported':list(SUPPORTED_VERSIONS),'requested':params.get('protocolVersion')})
            if not isinstance(params.get('capabilities'),dict) or not isinstance(params.get('clientInfo'),dict):
                return rpc_error(request_id,-32602,'Invalid initialize parameters')
            self.legacy_initialized=True
            return {'jsonrpc':'2.0','id':request_id,'result':{
                'protocolVersion':params['protocolVersion'],
                'capabilities':{'tools':{'listChanged':False}},
                'serverInfo':{'name':SERVER_NAME,'version':SERVER_VERSION},
                'instructions':'Read/draft-only local MCP. Execute only if trusted host enables --allow-execute. No remote accounts, spending or publication.'}}

        modern=(method=='server/discover' or isinstance(params.get('_meta'),dict))
        if modern:
            problem=self._require_meta(params,request_id)
            if problem: return problem
        elif not self.legacy_initialized:
            return rpc_error(request_id,-32002,'MCP legacy client must initialize first')

        if method=='server/discover':
            result={'resultType':'complete','supportedVersions':list(SUPPORTED_VERSIONS),
                    'capabilities':{'tools':{'listChanged':False}},
                    '_meta':{'io.modelcontextprotocol/serverInfo':{'name':SERVER_NAME,'version':SERVER_VERSION}},
                    'instructions':'Offline/local only. No arbitrary filesystem, HTTP, code execution, deployment or spending.',
                    'ttlMs':300000,'cacheScope':'private'}
        elif method=='ping':
            result={'resultType':'complete'} if modern else {}
        elif method=='tools/list':
            cursor=params.get('cursor')
            if cursor is not None:
                return rpc_error(request_id,-32602,'Pagination not needed; cursor unsupported')
            result={'tools':TOOLS}
            if modern:
                result={'resultType':'complete',**result,'cacheScope':'private','ttlMs':300000}
        elif method=='tools/call':
            name=params.get('name')
            args=params.get('arguments',{})
            if name not in TOOL_NAMES:
                return rpc_error(request_id,-32602,'Unknown tool')
            if not isinstance(args,dict):
                return rpc_error(request_id,-32602,'Tool arguments must be an object')
            schema=next(t['inputSchema'] for t in TOOLS if t['name']==name)
            for key in schema.get('required',[]):
                if key not in args:
                    return rpc_error(request_id,-32602,'Missing required argument: '+key)
            extra=set(args)-set(schema.get('properties',{}))
            if extra:
                return rpc_error(request_id,-32602,'Unsupported argument(s): '+', '.join(sorted(extra)))
            try:
                result=self.call_tool(name,args,modern=modern)
            except (ValueError,TypeError,KeyError) as exc:
                result=tool_result({'error':str(exc)[:400]},failed=True,modern=modern)
            except Exception:
                result=tool_result({'error':'Internal execution error; consult trusted host logs'},failed=True,modern=modern)
        else:
            return rpc_error(request_id,-32601,'Unknown method')
        return {'jsonrpc':'2.0','id':request_id,'result':result}


def parse_message(raw, server):
    if isinstance(raw, bytes):
        try:
            raw=raw.decode('utf-8')
        except UnicodeError:
            return rpc_error(None,-32700,'Invalid UTF-8')
    if len(raw.encode('utf-8'))>MAX_MESSAGE_BYTES:
        return rpc_error(None,-32600,'Message too large')
    try:
        msg=json.loads(raw)
    except (ValueError,TypeError):
        return rpc_error(None,-32700,'Invalid JSON')
    return server.handle(msg)


def serve_stdio(server):
    inp=sys.stdin.buffer
    out=sys.stdout.buffer
    while True:
        raw=inp.readline(MAX_MESSAGE_BYTES+2)
        if not raw:
            break
        if len(raw)>MAX_MESSAGE_BYTES:
            # Drain oversized input line to keep framing intact.
            while raw and not raw.endswith(b'\n'):
                raw=inp.readline(MAX_MESSAGE_BYTES+2)
            response=rpc_error(None,-32600,'Message too large')
        else:
            response=parse_message(raw,server)
        if response is not None:
            out.write((json.dumps(response,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8'))
            out.flush()


def main(argv=None):
    p=argparse.ArgumentParser(description='Nümtema Synapse MCP local stdio server')
    p.add_argument('--allow-execute',action='store_true',help='Explicitly allow only registered local read/draft tools')
    p.add_argument('--state-db',type=Path,help='Opt in to SQLite receipts/events of local runs')
    p.add_argument('--lessons-db',type=Path,help='Opt in to read a local SQLite lessons database')
    p.add_argument('--max-calls-per-minute',type=int,default=100)
    args=p.parse_args(argv)
    if not 1<=args.max_calls_per_minute<=1000:
        p.error('--max-calls-per-minute must be 1..1000')
    serve_stdio(SynapseMCPServer(allow_execute=args.allow_execute,state_db=args.state_db,
                                lessons_db=args.lessons_db,max_calls_per_minute=args.max_calls_per_minute))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
