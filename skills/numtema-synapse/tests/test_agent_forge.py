import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from agent_forge import AgentForge
from forge_runtime import ForgeRuntime


class AgentForgeTests(unittest.TestCase):
    def test_compiles_roles_into_valid_cor_contracts(self):
        blueprint={'mission_id':'M-1','context':{'offer':'Audit PME'},'steps':[
            {'id':'brief','agent_id':'FocusAgent','objective':'Capture brief',
             'tool':'local.extract_fields','params':{'data':{'offer':'Audit PME'},'fields':['offer']},
             'checks':{'required_keys':['offer']}},
            {'id':'draft','agent_id':'Rhetorica','objective':'Write draft',
             'tool':'local.render_template','depends_on':['brief'],
             'params':{'template':'Pour {{offer}}', 'values_from_task':'brief'},
             'checks':{'required_keys':['text']}}
        ]}
        mission=AgentForge().compile(blueprint)
        self.assertEqual(len(mission['tasks']),2)
        self.assertEqual(mission['tasks'][1]['contract']['identity']['agent_id'],'Rhetorica')
        self.assertEqual(ForgeRuntime().run(mission,execute=True)['status'],'COMPLETED')

    def test_does_not_grant_external_permissions_from_blueprint(self):
        blueprint={'mission_id':'M-2','steps':[{'id':'post','agent_id':'PublisherAgent',
             'objective':'Post content','tool':'external.publish',
             'permissions':{'external_write':True},'params':{}}]}
        with self.assertRaises(ValueError):
            AgentForge().compile(blueprint)

    def test_sensitive_tool_is_marked_approval_required(self):
        blueprint={'mission_id':'M-3','steps':[{'id':'publish','agent_id':'PublisherAgent',
             'objective':'Publish','tool':'external.publish','capability':'external_write'}]}
        t=AgentForge().compile(blueprint)['tasks'][0]
        self.assertFalse(t['contract']['permissions']['external_write'])
        self.assertIn('external_write',t['contract']['permissions']['require_approval'])

if __name__=='__main__': unittest.main()
