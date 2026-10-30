import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from llm_runtime import (OllamaBackend, PrivateAgentRuntime, validate_endpoint,
                         AgentBudgetExceeded, load_mission)


class FakeLLM:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def complete(self, messages, *, model, max_output_tokens, timeout_seconds):
        self.calls.append({'messages': messages, 'model': model, 'limit': max_output_tokens})
        return self.outputs.pop(0)


BLUEPRINT = {
    'mission_id': 'demo-private-001',
    'context': {'project': 'Démonstration fictive', 'audience': 'PME'},
    'steps': [
        {'id': 'draft', 'agent_id': 'Rhetorica', 'objective': 'Rédiger une proposition de valeur',
         'tool': 'llm.draft', 'depends_on': [],
         'params': {'instructions': 'Utiliser un titre et une promesse sans preuve inventée'},
         'expected_keys': ['text'],
         'checks': {'required_keys': ['text'], 'required_text': ['HERO', 'CTA']},
         'max_revisions': 1},
    ]
}


class RuntimeTests(unittest.TestCase):
    def test_default_rejects_non_loopback_url(self):
        for bad in ['http://example.com:11434', 'http://169.254.169.254/latest',
                    'file:///etc/passwd', 'http://user:pass@localhost:11434',
                    'http://127.0.0.1:11434/redirect', 'https://localhost:11434']:
            with self.subTest(url=bad), self.assertRaises(ValueError):
                validate_endpoint(bad)

    def test_trusted_host_requires_explicit_opt_in(self):
        self.assertEqual(validate_endpoint('http://ollama:11434',trusted_hosts=('ollama',)),
                         'http://ollama:11434/api/chat')
        with self.assertRaises(ValueError):
            validate_endpoint('http://ollama:11434')

    def test_dry_run_does_not_call_llm(self):
        fake=FakeLLM([])
        runtime=PrivateAgentRuntime(fake, model='example:local')
        report=runtime.run(BLUEPRINT, execute=False)
        self.assertEqual(report['status'], 'PLANNED')
        self.assertEqual(len(fake.calls), 0)

    def test_executes_model_and_reinjects_reflexion_feedback(self):
        fake=FakeLLM([{'text': 'HERO : Offre'}, {'text': 'HERO : Offre claire. CTA : Réserver.'}])
        report=PrivateAgentRuntime(fake, model='example:local').run(BLUEPRINT, execute=True)
        self.assertEqual(report['status'], 'COMPLETED')
        self.assertEqual(report['tasks']['draft']['attempts'], 2)
        self.assertEqual(len(fake.calls), 2)
        self.assertIn('CTA', json.dumps(fake.calls[1]['messages'],ensure_ascii=False))
        self.assertIn('text',fake.calls[0]['messages'][0]['content'])

    def test_call_limit_is_bounded(self):
        fake=FakeLLM([{'text':'HERO'}])
        r=PrivateAgentRuntime(fake,model='local',max_calls=1).run(BLUEPRINT,execute=True)
        self.assertEqual(r['status'],'FAILED')
        self.assertEqual(len(fake.calls),1)

    def test_no_arbitrary_tools_from_blueprint(self):
        b=json.loads(json.dumps(BLUEPRINT))
        b['steps'][0]['tool']='shell.execute'
        fake=FakeLLM([])
        r=PrivateAgentRuntime(fake,model='local').run(b,execute=True)
        self.assertEqual(r['status'],'BLOCKED')
        self.assertEqual(len(fake.calls),0)

    def test_empty_model_name_rejected(self):
        with self.assertRaises(ValueError): PrivateAgentRuntime(FakeLLM([]),model='')

    def test_mission_size_rejected(self):
        fake=FakeLLM([])
        runtime=PrivateAgentRuntime(fake,model='test')
        b=json.loads(json.dumps(BLUEPRINT)); b['context']['secret']='X'*1000000
        report=runtime.run(b,execute=False)
        self.assertEqual(report['status'],'BLOCKED')

    def test_result_never_claims_verified_facts_from_llm_alone(self):
        fake=FakeLLM([{'text':'HERO - CTA', 'claim':'tested'}])
        result=PrivateAgentRuntime(fake,model='test').run(BLUEPRINT,execute=True)
        self.assertEqual(result['status'],'COMPLETED')
        self.assertEqual(result['assurance'],'structural_only')

    def test_external_network_not_exposed_in_public_tools(self):
        from public_mcp_policy import PUBLIC_TOOL_NAMES
        self.assertNotIn('llm.draft',PUBLIC_TOOL_NAMES)
        self.assertNotIn('numtema.private.execute',PUBLIC_TOOL_NAMES)

    def test_ollama_http_protocol_json_wire(self):
        requests=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                size=int(self.headers['Content-Length']); body=json.loads(self.rfile.read(size))
                requests.append((self.path,body))
                raw=json.dumps({'message':{'role':'assistant','content':json.dumps({'text':'HERO : A. CTA : B.'})}}).encode()
                self.send_response(200); self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(raw))); self.end_headers();self.wfile.write(raw)
            def log_message(self,*args):pass
        srv=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        runner=threading.Thread(target=srv.serve_forever,daemon=True);runner.start()
        try:
            backend=OllamaBackend(f'http://127.0.0.1:{srv.server_port}')
            result=backend.complete([{'role':'user','content':'Test'}],model='local',max_output_tokens=99,timeout_seconds=3)
            self.assertEqual(result['text'],'HERO : A. CTA : B.')
            self.assertEqual(requests[0][0],'/api/chat')
            self.assertEqual(requests[0][1]['format'],'json')
            self.assertFalse(requests[0][1]['stream'])
            self.assertNotIn('tools',requests[0][1])
        finally:
            srv.shutdown();srv.server_close();runner.join(timeout=2)

    def test_cli_end_to_end_with_fake_ollama_http(self):
        import subprocess
        import tempfile
        requests=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                size=int(self.headers['Content-Length']); payload=json.loads(self.rfile.read(size))
                requests.append(payload)
                body=json.dumps({'message':{'content':json.dumps({'text':'HERO : Démo. BÉNÉFICE : Clair. CTA : Réserver.'})}}).encode()
                self.send_response(200); self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
            def log_message(self,*args):pass
        srv=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        runner=threading.Thread(target=srv.serve_forever,daemon=True); runner.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                blueprint=Path(__file__).resolve().parents[1]/'examples/blueprint-local-llm.json'
                cli=Path(__file__).resolve().parents[1]/'scripts/llm_runtime.py'
                cmd=[sys.executable,str(cli),str(blueprint),'--model','demo-local',
                     '--url',f'http://127.0.0.1:{srv.server_port}']
                dry=subprocess.run(cmd,capture_output=True,text=True,timeout=10)
                self.assertEqual(dry.returncode,0,dry.stderr)
                self.assertEqual(json.loads(dry.stdout)['status'],'PLANNED')
                self.assertEqual(len(requests),0)
                execution=subprocess.run(cmd+['--execute'],capture_output=True,text=True,timeout=15)
                self.assertEqual(execution.returncode,0,execution.stderr)
                result=json.loads(execution.stdout)
                self.assertEqual(result['status'],'COMPLETED')
                self.assertEqual(result['model_calls'],1)
                self.assertEqual(result['tasks']['review']['output']['passed'],True)
                self.assertEqual(len(requests),1)
        finally:
            srv.shutdown();srv.server_close();runner.join(timeout=2)

    def test_load_mission_accepts_blueprint_and_compiled(self):
        mission=load_mission(BLUEPRINT)
        self.assertEqual(mission['tasks'][0]['tool'],'llm.draft')
        self.assertEqual(load_mission(mission)['mission_id'],mission['mission_id'])

if __name__=='__main__':unittest.main()
