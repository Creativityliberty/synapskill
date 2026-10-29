"""MCP protocol and runtime security regression tests (no network, fake client)."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'scripts'))
from mcp_server import SynapseMCPServer, parse_message

BLUEPRINT = json.loads((BASE/'examples/blueprint-landing-page.json').read_text(encoding='utf-8'))
MODERN_META = {"io.modelcontextprotocol/protocolVersion": "2026-07-28",
               "io.modelcontextprotocol/clientInfo": {"name":"test","version":"1"},
               "io.modelcontextprotocol/clientCapabilities": {}}

def modern(method, params=None, id=1, version="2026-07-28"):
    met = dict(MODERN_META)
    met['io.modelcontextprotocol/protocolVersion'] = version
    return {'jsonrpc':'2.0','id':id,'method':method,'params':{**(params or {}),'_meta':met}}

class TestModernMCP(unittest.TestCase):
    def setUp(self):
        self.s = SynapseMCPServer()

    def test_discover(self):
        result=self.s.handle(modern('server/discover'))['result']
        self.assertEqual(result['resultType'],'complete')
        self.assertIn('2026-07-28',result['supportedVersions'])
        self.assertIn('tools',result['capabilities'])

    def test_list_tools_is_deterministic(self):
        one=self.s.handle(modern('tools/list'))['result']
        two=self.s.handle(modern('tools/list'))['result']
        self.assertEqual(one,two)
        names=[x['name'] for x in one['tools']]
        self.assertEqual(names,sorted(names))
        self.assertIn('numtema.execute_workflow',names)
        self.assertTrue(all(x['inputSchema']['type']=='object' for x in one['tools']))

    def test_compile_blueprint_returns_real_contracts(self):
        result=self.s.handle(modern('tools/call',{'name':'numtema.compile_blueprint','arguments':{'blueprint':BLUEPRINT}}))['result']
        self.assertFalse(result['isError'])
        self.assertEqual(len(result['structuredContent']['tasks']),3)

    def test_plan_compiled_mission(self):
        compile_result=self.s.call_tool('numtema.compile_blueprint',{'blueprint':BLUEPRINT})
        mission=compile_result['structuredContent']
        plan=self.s.call_tool('numtema.plan_workflow',{'mission':mission})
        self.assertEqual(plan['structuredContent']['status'],'PLANNED')
        self.assertEqual(plan['structuredContent']['order'],['brief','copy','quality_gate'])

    def test_execution_denied_by_default(self):
        mission=self.s.call_tool('numtema.compile_blueprint',{'blueprint':BLUEPRINT})['structuredContent']
        output=self.s.call_tool('numtema.execute_workflow',{'mission':mission})
        self.assertTrue(output['isError'])
        self.assertIn('disabled',output['content'][0]['text'].lower())

    def test_execution_opt_in_and_bounded(self):
        s=SynapseMCPServer(allow_execute=True)
        mission=s.call_tool('numtema.compile_blueprint',{'blueprint':BLUEPRINT})['structuredContent']
        result=s.call_tool('numtema.execute_workflow',{'mission':mission})
        self.assertEqual(result['structuredContent']['status'],'COMPLETED')
        self.assertEqual(result['structuredContent']['tasks']['copy']['attempts'],1)

    def test_never_accept_grants_from_caller(self):
        s=SynapseMCPServer(allow_execute=True)
        mission=s.call_tool('numtema.compile_blueprint',{'blueprint':BLUEPRINT})['structuredContent']
        r=s.handle(modern('tools/call',{'name':'numtema.execute_workflow',
                     'arguments':{'mission':mission,'grants':['*']}}))
        self.assertEqual(r['error']['code'],-32602)

    def test_sensitive_unregistered_tool_denied_even_in_opt_in_mode(self):
        s=SynapseMCPServer(allow_execute=True)
        mission=s.call_tool('numtema.compile_blueprint',{'blueprint':BLUEPRINT})['structuredContent']
        mission['tasks'][0]['tool']='local.external_transfer'
        mission['tasks'][0]['contract']['tools']['allowlist']=['local.external_transfer']
        mission['tasks'][0]['contract']['permissions']['requested_tools']=['local.external_transfer']
        result=s.call_tool('numtema.execute_workflow',{'mission':mission})
        self.assertEqual(result['structuredContent']['status'],'BLOCKED')
        self.assertIn('not registered',str(result['structuredContent']['issues']))

    def test_validate_cor_invalid_result(self):
        out=self.s.call_tool('numtema.validate_cor',{'contract':{}})
        self.assertFalse(out['structuredContent']['valid'])
        self.assertGreater(len(out['structuredContent']['issues']),0)

    def test_version_unsupported(self):
        r=self.s.handle(modern('tools/list',version='2099-01-01'))
        self.assertEqual(r['error']['code'],-32022)
        self.assertIn('2026-07-28',r['error']['data']['supported'])

    def test_invalid_modern_meta(self):
        r=self.s.handle({'jsonrpc':'2.0','id':1,'method':'tools/list','params':{'_meta':{'io.modelcontextprotocol/protocolVersion':'2026-07-28'}}})
        self.assertIn('error',r)

    def test_unknown_tool(self):
        r=self.s.handle(modern('tools/call',{'name':'numtema.make_payments','arguments':{}}))
        self.assertEqual(r['error']['code'],-32602)

    def test_no_shell_file_http_tools_exposed(self):
        tools=self.s.handle(modern('tools/list'))['result']['tools']
        self.assertFalse(any('shell' in t['name'] or 'http' in t['name'] or 'publish' in t['name'] for t in tools))

    def test_rate_limit(self):
        s=SynapseMCPServer(max_calls_per_minute=2)
        self.assertIn('result',s.handle(modern('tools/list')))
        self.assertIn('result',s.handle(modern('tools/list',id=2)))
        self.assertIn('error',s.handle(modern('tools/list',id=3)))

    def test_bad_tool_arguments_return_error(self):
        r=self.s.handle(modern('tools/call',{'name':'numtema.compile_blueprint','arguments':{'blueprint':'not-object'}}))
        self.assertTrue(r['result']['isError'])

    def test_optional_memory_not_configured(self):
        r=self.s.call_tool('numtema.recall_lessons',{'scope':'marketing'})
        self.assertFalse(r['isError'])
        self.assertEqual(r['structuredContent']['status'],'NOT_CONFIGURED')

    def test_extra_arguments_rejected(self):
        r=self.s.handle(modern('tools/call',{'name':'numtema.list_agents','arguments':{'token':'secret'}}))
        self.assertEqual(r['error']['code'],-32602)

    def test_bad_mission_checks_fail_gracefully(self):
        s=SynapseMCPServer(allow_execute=True)
        mission=s.call_tool('numtema.compile_blueprint',{'blueprint':BLUEPRINT})['structuredContent']
        mission['tasks'][0]['checks']={'required_keys':5}
        r=s.call_tool('numtema.execute_workflow',{'mission':mission})
        self.assertEqual(r['structuredContent']['status'],'BLOCKED')
        self.assertIn('checks.required_keys',str(r['structuredContent']['issues']))

    def test_empty_tool_params_invalid(self):
        r=self.s.handle(modern('tools/call',{'name':'numtema.list_agents','arguments':[]}))
        self.assertEqual(r['error']['code'],-32602)

class TestLegacyMCP(unittest.TestCase):
    def test_initialize_then_ready(self):
        s=SynapseMCPServer()
        init=s.handle({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'legacy','version':'1'}}})
        self.assertEqual(init['result']['protocolVersion'],'2025-11-25')
        self.assertIsNone(s.handle({'jsonrpc':'2.0','method':'notifications/initialized'}))
        response=s.handle({'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}})
        self.assertGreater(len(response['result']['tools']),0)
        self.assertNotIn('resultType',response['result'])

    def test_legacy_requires_init(self):
        s=SynapseMCPServer()
        r=s.handle({'jsonrpc':'2.0','id':1,'method':'tools/list','params':{}})
        self.assertIn('error',r)

    def test_legacy_tool_result(self):
        s=SynapseMCPServer()
        s.handle({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'client','version':'1'}}})
        result=s.handle({'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'numtema.list_agents','arguments':{}}})
        self.assertIn('structuredContent',result['result'])
        self.assertNotIn('resultType',result['result'])

class TestWire(unittest.TestCase):
    def test_malformed_json(self):
        r=parse_message('{oops',SynapseMCPServer())
        self.assertEqual(r['error']['code'],-32700)
    def test_batch_rejected(self):
        r=parse_message('[]',SynapseMCPServer())
        self.assertEqual(r['error']['code'],-32600)
    def test_notifications_do_not_yield_response(self):
        self.assertIsNone(SynapseMCPServer().handle({'jsonrpc':'2.0','method':'notifications/initialized'}))

    def test_real_stdio_wire_conversation(self):
        executable=BASE/'scripts/mcp_server.py'
        lines=[modern('server/discover',id=10),
               modern('tools/list',id=11),
               modern('tools/call',{'name':'numtema.list_agents','arguments':{}},id=12)]
        raw=''.join(json.dumps(x)+'\n' for x in lines)
        p=subprocess.run([sys.executable,str(executable)],input=raw,text=True,
                         capture_output=True,timeout=6)
        self.assertEqual(p.returncode,0,p.stderr)
        output=[json.loads(line) for line in p.stdout.splitlines()]
        self.assertEqual([x['id'] for x in output],[10,11,12])
        self.assertEqual(output[0]['result']['resultType'],'complete')
        self.assertGreater(len(output[2]['result']['structuredContent']['agents']),5)

    def test_real_stdio_legacy_conversation(self):
        executable=BASE/'scripts/mcp_server.py'
        lines=[{'jsonrpc':'2.0','id':1,'method':'initialize',
                'params':{'protocolVersion':'2025-11-25','capabilities':{},
                          'clientInfo':{'name':'host','version':'1'}}},
               {'jsonrpc':'2.0','method':'notifications/initialized'},
               {'jsonrpc':'2.0','id':2,'method':'tools/list'}]
        p=subprocess.run([sys.executable,str(executable)],input=''.join(json.dumps(x)+'\n' for x in lines),
                         text=True,capture_output=True,timeout=6)
        self.assertEqual(p.returncode,0,p.stderr)
        output=[json.loads(line) for line in p.stdout.splitlines()]
        self.assertEqual([x['id'] for x in output],[1,2])
        self.assertEqual(output[0]['result']['protocolVersion'],'2025-11-25')

if __name__=='__main__': unittest.main()
