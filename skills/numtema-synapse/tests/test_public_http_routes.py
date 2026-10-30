"""FastAPI HTTP public policy, with SSE transport using same MCP engine."""
import sys
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from mcp_server import MODERN_VERSION, META_VERSION
from mcp_http_server import app, sse_clients

META={META_VERSION:MODERN_VERSION,'io.modelcontextprotocol/clientInfo':{'name':'test','version':'1'},
      'io.modelcontextprotocol/clientCapabilities':{}}

def msg(method,**kwargs):
    return {'jsonrpc':'2.0','id':3,'method':method,'params':{'_meta':META,**kwargs}}

class HttpPolicyTests(unittest.TestCase):
    def setUp(self): self.client=TestClient(app)
    def test_health_shows_no_execution(self):
        r=self.client.get('/health')
        self.assertEqual(r.status_code,200)
        self.assertFalse(r.json()['execution_allowed'])

    def test_browser_lists_four_only(self):
        s=self.client.get('/mcp').text
        self.assertIn('numtema.compile_blueprint',s)
        self.assertNotIn('numtema.execute_workflow',s)
        self.assertNotIn('numtema.recall_lessons',s)

    def test_http_tools_four(self):
        r=self.client.post('/mcp',json=msg('tools/list'))
        self.assertEqual(r.status_code,200)
        self.assertEqual(len(r.json()['result']['tools']),4)

    def test_http_denies_execution(self):
        r=self.client.post('/mcp',json=msg('tools/call',name='numtema.execute_workflow',arguments={'mission':{}}))
        self.assertIn('error',r.json())

    def test_http_denies_sqlite(self):
        r=self.client.post('/mcp',json=msg('tools/call',name='numtema.recall_lessons',arguments={'scope':'x'}))
        self.assertIn('error',r.json())

    def test_public_http_no_auth(self):
        r=self.client.post('/mcp',json=msg('tools/call',name='numtema.list_agents',arguments={}))
        self.assertFalse(r.json()['result']['isError'])

    def test_sse_messages_same_policy(self):
        import asyncio
        queue=asyncio.Queue()
        sse_clients['test-session']=queue
        try:
            r=self.client.post('/messages?session_id=test-session',json=msg('tools/call',name='numtema.execute_workflow',arguments={'mission':{}}))
            self.assertEqual(r.status_code,202)
            self.assertIn('error',queue.get_nowait())
        finally: sse_clients.pop('test-session',None)

    def test_reject_untrusted_origin(self):
        r=self.client.post('/mcp',json=msg('tools/list'),headers={'Origin':'https://evil.example'})
        self.assertEqual(r.status_code,403)

    def test_reject_body_over_limit(self):
        r=self.client.post('/mcp',content=b'x'*1000100,headers={'Content-Type':'application/json'})
        self.assertEqual(r.status_code,413)

if __name__=='__main__': unittest.main()
