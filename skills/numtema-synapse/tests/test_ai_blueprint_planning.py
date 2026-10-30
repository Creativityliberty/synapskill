"""Public Mission Studio may PLAN private AI tasks but never EXECUTE them."""
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from agent_forge import AgentForge
from public_mcp_policy import PublicSynapseMCPServer

class AiPlanningTests(unittest.TestCase):
    def setUp(self):self.s=PublicSynapseMCPServer()

    def test_llm_draft_plan_is_valid_but_still_not_executable(self):
        bp={
            'mission_id':'AI-PLAN-PUBLIC', 'context':{'project':'fictif'},
            'steps':[{'id':'draft','agent_id':'Rhetorica','objective':'Rédiger en IA localement',
                      'tool':'llm.draft','params':{'instructions':'Texte original'},
                      'expected_keys':['text'],'checks':{'required_keys':['text']}}]}
        mission=AgentForge().compile(bp)
        result=self.s.call_tool('numtema.plan_workflow',{'mission':mission},modern=False)['structuredContent']
        self.assertEqual(result['status'],'PLANNED')
        self.assertEqual(result['order'],['draft'])
        self.assertFalse(self.s.allow_execute)
        denial=self.s.handle({'jsonrpc':'2.0','id':1,'method':'tools/call',
                              'params':{'name':'numtema.execute_workflow','arguments':{'mission':mission}}})
        self.assertIn('error',denial)

if __name__=='__main__':unittest.main()

