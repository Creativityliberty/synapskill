"""Contract-first tests for the private real-model smoke validation kit."""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / 'skills' / 'numtema-synapse' / 'scripts'
sys.path.insert(0, str(SCRIPTS))


class PrivateOllamaDeploymentTests(unittest.TestCase):
    def test_private_stack_has_no_host_ports_and_internal_network(self):
        stack = yaml.safe_load((ROOT / 'deployment/ollama-private.compose.yml').read_text())
        self.assertEqual(stack['networks']['synapse_private']['internal'], True)
        self.assertEqual(set(stack['services']), {'ollama', 'worker'})
        for name, service in stack['services'].items():
            self.assertNotIn('ports', service, name)
            self.assertNotIn('expose', service, name)
            self.assertEqual(service['networks'], ['synapse_private'])
            self.assertNotIn('privileged', service)
        self.assertEqual(stack['services']['worker']['profiles'], ['manual'])
        self.assertTrue(stack['services']['worker']['read_only'])
        self.assertIn('no-new-privileges:true', stack['services']['worker']['security_opt'])
        self.assertEqual(stack['services']['worker']['cap_drop'], ['ALL'])
        self.assertNotIn('SYNAPSE_ALLOW_EXECUTE', str(stack))

    def test_bootstrap_has_egress_but_no_exposed_ports(self):
        stack = yaml.safe_load((ROOT / 'deployment/ollama-bootstrap.compose.yml').read_text())
        self.assertNotIn('ports', stack['services']['ollama'])
        self.assertNotIn('expose', stack['services']['ollama'])
        self.assertEqual(stack['volumes']['ollama_models']['name'], 'synapse_private_ollama_models')
        self.assertEqual(stack['services']['ollama']['volumes'], ['ollama_models:/root/.ollama'])

    def test_live_probe_requires_opt_in_and_never_dials_without_it(self):
        proc = subprocess.run([sys.executable, str(SCRIPTS / 'private_live_probe.py'),
                               '--model','gemma3:1b'], cwd=ROOT, text=True, capture_output=True)
        self.assertNotEqual(proc.returncode, 0)
        output = json.loads(proc.stdout)
        self.assertEqual(output['status'], 'NOT_EXECUTED')
        self.assertEqual(output['model_calls'], 0)

    def test_live_probe_uses_canonical_validation_not_arbitrary_url(self):
        from private_live_probe import probe
        with self.assertRaises(ValueError):
            probe('gemma3:1b', 'http://evil.example:11434', [], True, 120)

    def test_private_probe_true_api_calls_with_local_fixture(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from private_live_probe import probe
        calls=[]

        class FakeOllama(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_GET(self):
                self.assert_tag = self.path
                data = {'models':[{'name':'gemma3:1b'}]} if self.path=='/api/tags' else {}
                body=json.dumps(data).encode('utf-8')
                self.send_response(200);self.send_header('Content-Length',str(len(body)))
                self.end_headers();self.wfile.write(body)
            def do_POST(self):
                selfpath=self.path
                payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                calls.append((selfpath,payload))
                if len(calls)==1: reply={'probe':'synapse'}
                elif len(calls)==2: reply={'text':'HERO : Offre fictive. BÉNÉFICE : Clarté. CTA : Réserver.'}
                else: reply={'passed':True,'issues':[],'suggestions':[]}
                body=json.dumps({'message':{'content':json.dumps(reply)}}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(body)))
                self.end_headers();self.wfile.write(body)

        server=ThreadingHTTPServer(('127.0.0.1',0),FakeOllama)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            out=probe('gemma3:1b', f'http://127.0.0.1:{server.server_port}',[],True,3)
            self.assertEqual(out['status'],'GO',out)
            self.assertTrue(out['checks']['cor_reflexion'])
            self.assertGreaterEqual(out['model_calls'],3)
            self.assertEqual(len(calls),3)
            self.assertTrue(all(path=='/api/chat' for path,_ in calls))
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)

    def test_missing_model_fails_closed_without_chat(self):
        import threading
        from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
        from private_live_probe import probe
        class TagOnly(BaseHTTPRequestHandler):
            def log_message(self,*_):pass
            def do_GET(self):
                raw=json.dumps({'models':[]}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(raw)))
                self.end_headers();self.wfile.write(raw)
            def do_POST(self):raise AssertionError('Should never use chat without model')
        server=ThreadingHTTPServer(('127.0.0.1',0),TagOnly)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            out=probe('gemma3:1b',f'http://127.0.0.1:{server.server_port}',[],True,3)
            self.assertEqual(out['status'],'NO_GO')
            self.assertEqual(out['reason'],'model_not_installed')
            self.assertEqual(out['model_calls'],0)
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)

    def test_report_summarizer_rejects_unreviewed_completed(self):
        from private_live_probe import summarize_workflow
        outcome = {'status':'COMPLETED', 'model_calls':1, 'tasks':{'draft':{'status':'COMPLETED'}}, 'reflexion':{}}
        summary = summarize_workflow(outcome)
        self.assertEqual(summary['status'],'NO_GO')
        self.assertEqual(summary['reason'],'missing_passed_reflexion')


if __name__ == '__main__':
    unittest.main()
