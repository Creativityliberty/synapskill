"""Public HTTP/SSE exposure must be safe with no authentication."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from mcp_server import MODERN_VERSION, META_VERSION

META = {META_VERSION: MODERN_VERSION,
        'io.modelcontextprotocol/clientInfo': {'name': 'test-client', 'version':'1'},
        'io.modelcontextprotocol/clientCapabilities': {}}


def rpc(method, **kwargs):
    return {'jsonrpc':'2.0','id':4,'method':method,'params':{'_meta':META,**kwargs}}


class PublicPolicyTests(unittest.TestCase):
    def setUp(self):
        from public_mcp_policy import PublicSynapseMCPServer
        self.server = PublicSynapseMCPServer(max_calls_per_minute=100)

    def test_tools_list_exact_four(self):
        result = self.server.handle(rpc('tools/list'))
        names = {t['name'] for t in result['result']['tools']}
        self.assertEqual(names, {'numtema.list_agents','numtema.validate_cor',
                                 'numtema.compile_blueprint','numtema.plan_workflow'})

    def test_execution_denied_not_only_hidden(self):
        result = self.server.handle(rpc('tools/call',name='numtema.execute_workflow',arguments={'mission':{}}))
        self.assertIn('error',result)
        self.assertNotIn('result',result)

    def test_sqlite_lessons_denied(self):
        result = self.server.handle(rpc('tools/call',name='numtema.recall_lessons',arguments={'scope':'anything'}))
        self.assertIn('error',result)

    def test_fake_identity_and_permissions_ignored(self):
        payload=rpc('tools/call',name='numtema.execute_workflow',arguments={'mission':{},'permission':'admin'})
        payload['params']['_meta']['X-Forwarded-User']='admin'
        self.assertIn('error',self.server.handle(payload))

    def test_public_tool_still_works(self):
        result=self.server.handle(rpc('tools/call',name='numtema.list_agents',arguments={}))
        self.assertFalse(result['result']['isError'])

    def test_invalid_jsonrpc_shape_returns_error_without_crashing(self):
        self.assertIn('error', self.server.handle([]))
        self.assertIn('error', self.server.handle(None))

    def test_never_creates_storage(self):
        self.assertIsNone(self.server.lessons)
        self.assertIsNone(self.server.runtime.state_db if hasattr(self.server.runtime,'state_db') else None)


if __name__ == '__main__': unittest.main()
