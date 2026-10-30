"""Acceptance contract for branded, accessible browser diagnostics."""
import sys
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from mcp_http_server import app

class PublicDashboardTests(unittest.TestCase):
    def setUp(self): self.client=TestClient(app)
    def test_browser_page_is_branded_not_a_placeholder(self):
        r=self.client.get('/mcp')
        self.assertEqual(r.status_code,200)
        self.assertIn('Nümtema Synapse',r.text)
        self.assertIn('id="diagnose"',r.text)
        self.assertIn('id="tools"',r.text)
        self.assertIn('id="endpoints"',r.text)
        self.assertIn('aria-live="polite"',r.text)
        self.assertIn('/assets/synapse.css',r.text)
        self.assertIn('/assets/synapse.js',r.text)
        self.assertNotIn('numtema.execute_workflow',r.text)
        self.assertNotIn('numtema.recall_lessons',r.text)
    def test_ui_assets_serve_correct_types(self):
        css=self.client.get('/assets/synapse.css')
        js=self.client.get('/assets/synapse.js')
        self.assertEqual(css.status_code,200)
        self.assertIn('text/css',css.headers['content-type'])
        self.assertIn('javascript',js.headers['content-type'])
        self.assertIn('grid-template-columns',css.text)
        self.assertIn('fetch(',js.text)
        self.assertNotIn('unpkg.com',css.text+js.text)
    def test_same_origin_browser_can_post_anonymously(self):
        from mcp_server import MODERN_VERSION, META_VERSION
        body={'jsonrpc':'2.0','id':1,'method':'tools/list','params':{'_meta':{
          META_VERSION:MODERN_VERSION,
          'io.modelcontextprotocol/clientInfo':{'name':'synapse-dashboard','version':'0.4.1'},
          'io.modelcontextprotocol/clientCapabilities':{}
        }}}
        r=self.client.post('/mcp',json=body,headers={'Origin':'http://testserver'})
        self.assertEqual(r.status_code,200)
        self.assertEqual(len(r.json()['result']['tools']),4)
    def test_security_headers(self):
        r=self.client.get('/mcp')
        self.assertIn('content-security-policy',r.headers)
        self.assertIn('frame-ancestors',r.headers['content-security-policy'])
        self.assertNotIn("'unsafe-inline'",r.headers['content-security-policy'])

if __name__=='__main__':unittest.main()
