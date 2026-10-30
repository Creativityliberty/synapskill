"""Mission Studio v0.5 acceptance tests: public planning only, no execution."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from mcp_http_server import app
from mcp_server import MODERN_VERSION, META_VERSION

META = {META_VERSION: MODERN_VERSION,
        'io.modelcontextprotocol/clientInfo': {'name': 'mission-studio-test', 'version':'0.5.0'},
        'io.modelcontextprotocol/clientCapabilities': {}}


def request(method, **data):
    return {'jsonrpc':'2.0', 'id':1, 'method':method, 'params':{'_meta':META, **data}}


class MissionStudioTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_studio_embedded_and_loaded_as_local_asset(self):
        html = self.client.get('/mcp')
        self.assertEqual(html.status_code, 200)
        for expected in ('id="studio"', 'id="mission-title"', 'id="mission-goal"',
                         'id="mission-preset"', 'id="studio-generate"',
                         'id="studio-export"', '/assets/mission-studio.js'):
            self.assertIn(expected, html.text)
        self.assertNotIn('action="/execute"', html.text)
        script = self.client.get('/assets/mission-studio.js')
        self.assertEqual(script.status_code, 200)
        self.assertIn('javascript', script.headers['content-type'])
        self.assertIn('numtema.compile_blueprint', script.text)
        self.assertIn('numtema.plan_workflow', script.text)
        self.assertIn('numtema.validate_cor', script.text)
        self.assertNotIn('numtema.execute_workflow', script.text)
        self.assertNotIn('localStorage', script.text)

    def test_public_mcp_compiles_and_plans_three_task_blueprint(self):
        blueprint = {
            'mission_id': 'STUDIO-FICTIVE-001',
            'context': {'origin': 'public_mission_studio', 'mode': 'landing_page', 'goal': 'Prototype fictif'},
            'steps': [
                {'id':'brief','agent_id':'FocusAgent','objective':'Structurer un brief fictif',
                 'tool':'local.extract_fields','capability':'read',
                 'params':{'data':{'offer':'Audit test','audience':'PME', 'benefit':'Clarté'},
                           'fields':['offer','audience','benefit']},
                 'checks':{'required_keys':['offer','audience','benefit']},
                 'expected_keys':['offer','audience','benefit']},
                {'id':'draft','agent_id':'Rhetorica','objective':'Proposer un contenu fictif',
                 'tool':'local.render_template','capability':'draft','depends_on':['brief'],
                 'params':{'values_from_task':'brief','template':'OFFRE {{offer}} / PUBLIC {{audience}} / BÉNÉFICE {{benefit}}'},
                 'checks':{'required_keys':['text'],'required_text':['OFFRE','BÉNÉFICE']},
                 'expected_keys':['text']},
                {'id':'review','agent_id':'VerifierAgent','objective':'Contrôle du contenu fictif',
                 'tool':'local.assert_contains','capability':'read','depends_on':['draft'],
                 'params':{'source_task':'draft','fragments':['OFFRE','BÉNÉFICE']},
                 'checks':{'required_keys':['passed','evidence'],'require_passed':True},
                 'expected_keys':['passed','evidence']}
            ]}
        compiled = self.client.post('/mcp', json=request('tools/call', name='numtema.compile_blueprint',
                                               arguments={'blueprint':blueprint})).json()
        self.assertIn('result', compiled)
        mission = compiled['result']['structuredContent']
        self.assertEqual(len(mission['tasks']), 3)
        self.assertTrue(all(t['contract']['permissions']['external_write'] is False
                            for t in mission['tasks']))
        planned = self.client.post('/mcp', json=request('tools/call', name='numtema.plan_workflow',
                                              arguments={'mission':mission})).json()['result']['structuredContent']
        self.assertEqual(planned['status'], 'PLANNED')
        self.assertEqual(planned['order'], ['brief','draft','review'])
        validated = self.client.post('/mcp', json=request('tools/call',name='numtema.validate_cor',
                                                 arguments={'contract': mission['tasks'][0]['contract']})).json()
        self.assertTrue(validated['result']['structuredContent']['valid'])

    def test_studio_does_not_enable_private_tools_or_origins(self):
        listed = self.client.post('/mcp', json=request('tools/list')).json()['result']['tools']
        self.assertEqual(len(listed), 4)
        denied = self.client.post('/mcp', json=request('tools/call', name='numtema.execute_workflow',arguments={'mission':{}}))
        self.assertIn('error', denied.json())
        foreign = self.client.post('/mcp', json=request('tools/list'), headers={'Origin':'https://untrusted.example'})
        self.assertEqual(foreign.status_code, 403)

if __name__ == '__main__': unittest.main()
