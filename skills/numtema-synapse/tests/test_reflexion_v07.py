"""Tests-first quality gate for private Reflexion v0.7."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from llm_runtime import PrivateAgentRuntime
from reflexion_engine import validate_verdict, ReflexionVerdictError

BLUEPRINT = {
    'mission_id': 'REFLEXION-07-DEMO',
    'context': {'project': 'Landing page fictive'},
    'steps': [{
        'id': 'draft', 'agent_id': 'Rhetorica', 'tool': 'llm.draft',
        'objective': 'Rédiger une page sans preuve inventée',
        'params': {'instructions': 'HERO puis CTA'},
        'expected_keys': ['text'],
        'checks': {'required_keys': ['text'], 'required_text': ['HERO', 'CTA']},
        'max_revisions': 1,
    }],
}

class FakeLLM:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []
    def complete(self, messages, *, model, max_output_tokens, timeout_seconds):
        self.calls.append({'model': model, 'messages': messages})
        return self.outputs.pop(0)

class ReflexionTests(unittest.TestCase):
    def test_verdict_must_be_typed_and_rejections_have_issues(self):
        for bad in [{'passed': 'true', 'issues': [], 'suggestions': []},
                    {'passed': False, 'issues': [], 'suggestions': []},
                    {'passed': True, 'issues': 'fine', 'suggestions': []},
                    {'passed': True, 'issues': [], 'suggestions': [], 'unexpected': 'foo'},
                    {'passed': True, 'issues': [], 'suggestions': [42]}]:
            with self.subTest(bad=bad), self.assertRaises(ReflexionVerdictError):
                validate_verdict(bad)

    def test_reviewer_passes_separate_invocation_and_uses_separate_model(self):
        model=FakeLLM([{'text':'HERO : Audit. CTA : Réserver.'},
                       {'passed':True,'issues':[],'suggestions':[]}])
        result=PrivateAgentRuntime(model,model='author:1',reviewer_model='critic:2',
                                   reflexion=True).run(BLUEPRINT,execute=True)
        self.assertEqual(result['status'],'COMPLETED')
        self.assertEqual(result['model_calls'],2)
        self.assertEqual([call['model'] for call in model.calls],['author:1','critic:2'])
        self.assertEqual(result['reflexion']['draft'][0]['status'],'PASSED')
        self.assertIn('HERO', json.dumps(model.calls[1]['messages'],ensure_ascii=False))
        self.assertEqual(result['assurance'],'structural_and_heuristic_review_only')
        self.assertNotIn('HERO', json.dumps(result['reflexion']['draft'][0]))

    def test_critic_rejects_then_feedback_reaches_retry(self):
        llm=FakeLLM([{'text':'HERO : Audit. CTA : Réserver.'},
                     {'passed':False,'issues':['Promesse non justifiée'],'suggestions':['Modérer la promesse']},
                     {'text':'HERO : Audit prudent. CTA : Réserver.'},
                     {'passed':True,'issues':[],'suggestions':[]}])
        report=PrivateAgentRuntime(llm,model='author',reflexion=True).run(BLUEPRINT,execute=True)
        self.assertEqual(report['status'],'COMPLETED')
        self.assertEqual(report['model_calls'],4)
        self.assertEqual(report['tasks']['draft']['attempts'],2)
        self.assertEqual([r['status'] for r in report['reflexion']['draft']],['REJECTED','PASSED'])
        self.assertIn('Promesse non justifiée',json.dumps(llm.calls[2]['messages'],ensure_ascii=False))

    def test_structural_failure_skips_review_before_retry(self):
        llm=FakeLLM([{'text':'HERO seulement'},
                     {'text':'HERO. CTA : Réserver.'},
                     {'passed':True,'issues':[],'suggestions':[]}])
        result=PrivateAgentRuntime(llm,model='author',reflexion=True).run(BLUEPRINT,execute=True)
        self.assertEqual(result['status'],'COMPLETED')
        self.assertEqual(result['model_calls'],3)
        self.assertEqual(result['reflexion']['draft'][0]['status'],'REJECTED_STRUCTURE')

    def test_invalid_verdict_fails_closed(self):
        llm=FakeLLM([{'text':'HERO. CTA'},
                     {'passed':'yes','issues':[],'suggestions':[]},
                     {'text':'HERO. CTA'},
                     {'passed':'yes','issues':[],'suggestions':[]}])
        result=PrivateAgentRuntime(llm,model='author',reflexion=True).run(BLUEPRINT,execute=True)
        self.assertEqual(result['status'],'FAILED')
        self.assertFalse(result['validation']['all_tasks_completed'])
        self.assertEqual(result['model_calls'],4)
        self.assertEqual([r['status'] for r in result['reflexion']['draft']],['REVIEW_INVALID','REVIEW_INVALID'])

    def test_call_budget_includes_review(self):
        llm=FakeLLM([{'text':'HERO. CTA'}])
        result=PrivateAgentRuntime(llm,model='author',reflexion=True,max_calls=1).run(BLUEPRINT,execute=True)
        self.assertEqual(result['status'],'FAILED')
        self.assertEqual(result['model_calls'],1)
        self.assertNotEqual(result.get('assurance'),'factually_verified')

    def test_dry_run_does_not_call_reviewer(self):
        llm=FakeLLM([])
        report=PrivateAgentRuntime(llm,model='author',reflexion=True).run(BLUEPRINT,execute=False)
        self.assertEqual(report['status'],'PLANNED')
        self.assertEqual(report['model_calls'],0)

    def test_private_cli_reflexion_over_local_http(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading
        import subprocess
        import tempfile
        observed=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                observed.append((self.path,data['model'],data['messages'][0]['role']))
                if data['model']=='reviewer:local':
                    content={'passed':True,'issues':[],'suggestions':[]}
                else:
                    content={'text':'HERO : Offre fictive. CTA : Réserver.'}
                payload=json.dumps({'message':{'content':json.dumps(content)}}).encode()
                self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            def log_message(self,*args): pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        t=threading.Thread(target=server.serve_forever,daemon=True)
        t.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                mission=Path(tmp)/'mission.json'
                mission.write_text(json.dumps(BLUEPRINT),encoding='utf-8')
                cli=Path(__file__).resolve().parents[1]/'scripts/llm_runtime.py'
                command=[sys.executable,str(cli),str(mission),'--model','writer:local',
                         '--reviewer-model','reviewer:local','--reflexion',
                         '--url',f'http://127.0.0.1:{server.server_port}']
                dry=subprocess.run(command,capture_output=True,text=True,timeout=8)
                self.assertEqual(dry.returncode,0,dry.stderr)
                self.assertEqual(json.loads(dry.stdout)['model_calls'],0)
                self.assertEqual(observed,[])
                run=subprocess.run(command+['--execute'],capture_output=True,text=True,timeout=12)
                self.assertEqual(run.returncode,0,run.stderr)
                report=json.loads(run.stdout)
                self.assertEqual(report['status'],'COMPLETED')
                self.assertEqual(report['reflexion']['draft'][0]['status'],'PASSED')
                self.assertEqual(report['model_calls'],2)
                self.assertEqual([(p,m) for p,m,_ in observed],
                                 [('/api/chat','writer:local'),('/api/chat','reviewer:local')])
        finally:
            server.shutdown(); server.server_close(); t.join(timeout=2)

    def test_public_tool_surface_remains_four(self):
        from public_mcp_policy import PUBLIC_TOOL_NAMES, PublicSynapseMCPServer
        self.assertEqual(len(PUBLIC_TOOL_NAMES),4)
        self.assertNotIn('llm.review',PUBLIC_TOOL_NAMES)
        self.assertNotIn('numtema.execute_workflow',PUBLIC_TOOL_NAMES)
        self.assertFalse(PublicSynapseMCPServer().allow_execute)

if __name__=='__main__':unittest.main()
