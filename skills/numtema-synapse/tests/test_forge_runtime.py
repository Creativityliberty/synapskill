import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from forge_runtime import ForgeRuntime, LessonMemory

TEMPLATE = json.loads((ROOT / 'examples' / 'cor-landing-page.json').read_text(encoding='utf-8'))


def task(task_id, tool='local.echo', depends=None, params=None, checks=None, *, revisions=0):
    contract = json.loads(json.dumps(TEMPLATE))
    contract['contract_id'] = f'COR-{task_id}'
    contract['identity']['agent_id'] = task_id
    contract['tools']['allowlist'] = [tool]
    contract['permissions']['requested_tools'] = [tool]
    contract['reflection']['max_revisions'] = revisions
    return {
        'id': task_id, 'contract': contract, 'tool': tool,
        'depends_on': depends or [], 'params': params or {'message': task_id},
        'checks': checks or {'required_keys': ['message']}
    }


def mission(*tasks):
    return {'version': '0.2.0', 'mission_id': 'TEST-01', 'tasks': list(tasks)}


class ForgeRuntimeTests(unittest.TestCase):
    def test_plan_never_executes(self):
        calls = []
        engine = ForgeRuntime()
        engine.register('internal.test', lambda p, u, f: calls.append('called') or {'message': 'hi'})
        result = engine.run(mission(task('t', tool='internal.test')), execute=False)
        self.assertEqual(result['status'], 'PLANNED')
        self.assertEqual(calls, [])

    def test_dag_runs_in_topological_order(self):
        seen = []
        engine = ForgeRuntime()
        engine.register('internal.observe', lambda p, u, f: seen.append((p['message'], list(u))) or {'message': p['message']})
        spec = mission(task('second', tool='internal.observe', depends=['first']),task('first', tool='internal.observe'))
        result = engine.run(spec, execute=True)
        self.assertEqual(result['status'], 'COMPLETED')
        self.assertEqual(seen, [('first', []),('second', ['first'])])

    def test_cycle_rejected_preflight(self):
        engine = ForgeRuntime()
        result = engine.run(mission(task('a',depends=['b']),task('b',depends=['a'])),execute=True)
        self.assertEqual(result['status'],'BLOCKED')
        self.assertIn('cycle',str(result['issues']).lower())

    def test_unknown_dep_rejected(self):
        result = ForgeRuntime().run(mission(task('a',depends=['missing'])),execute=True)
        self.assertEqual(result['status'],'BLOCKED')

    def test_undeclared_tool_not_run(self):
        t = task('x')
        t['contract']['tools']['allowlist'] = []
        result = ForgeRuntime().run(mission(t),execute=True)
        self.assertEqual(result['status'],'BLOCKED')

    def test_external_write_requires_host_grant(self):
        called = []
        engine = ForgeRuntime()
        engine.register('external.publish', lambda p,u,f: called.append('published') or {'message':'ok'}, capability='external_write')
        t = task('publish',tool='external.publish')
        t['contract']['permissions']['require_approval'] = ['external_write']
        result=engine.run(mission(t),execute=True)
        self.assertEqual(result['tasks']['publish']['status'],'BLOCKED')
        self.assertEqual(called, [])
        allowed=ForgeRuntime(grants={'TEST-01:publish:external.publish'})
        allowed.register('external.publish', lambda p,u,f: called.append('published') or {'message':'ok'}, capability='external_write')
        result2=allowed.run(mission(t),execute=True)
        self.assertEqual(result2['status'],'COMPLETED')
        self.assertEqual(called,['published'])

    def test_reflexion_feedback_influences_retry(self):
        incoming=[]
        def revise(params,upstream,feedback):
            incoming.append(list(feedback))
            if feedback:
                return {'message':'corrected','ready':True}
            return {'message':'draft'}
        engine=ForgeRuntime()
        engine.register('internal.revise',revise)
        t=task('draft',tool='internal.revise',checks={'required_keys':['ready']},revisions=2)
        result=engine.run(mission(t),execute=True)
        self.assertEqual(result['status'],'COMPLETED')
        self.assertEqual(result['tasks']['draft']['attempts'],2)
        self.assertTrue(incoming[1])

    def test_revision_limit_is_respected(self):
        calls=[]
        engine=ForgeRuntime()
        engine.register('internal.fail',lambda p,u,f: calls.append(1) or {'message':'not valid'})
        t=task('bad',tool='internal.fail',checks={'required_keys':['ready']},revisions=1)
        result=engine.run(mission(t),execute=True)
        self.assertEqual(result['status'],'FAILED')
        self.assertEqual(len(calls),2)

    def test_failed_task_blocks_dependents(self):
        engine=ForgeRuntime()
        t1=task('bad',checks={'required_keys':['not_present']})
        t2=task('dependent',depends=['bad'])
        r=engine.run(mission(t1,t2),execute=True)
        self.assertEqual(r['tasks']['dependent']['status'],'BLOCKED')

    def test_sqlite_cache_avoids_repeat_execution(self):
        with tempfile.TemporaryDirectory() as d:
            store=Path(d)/'missions.sqlite'
            hits=[]
            engine=ForgeRuntime(state_db=store)
            engine.register('internal.count',lambda p,u,f: hits.append(1) or {'message':'counted'})
            spec=mission(task('x',tool='internal.count'))
            self.assertEqual(engine.run(spec,execute=True)['status'],'COMPLETED')
            engine2=ForgeRuntime(state_db=store)
            engine2.register('internal.count',lambda p,u,f: hits.append(1) or {'message':'counted'})
            report=engine2.run(spec,execute=True)
            self.assertEqual(report['status'],'COMPLETED')
            self.assertTrue(report['tasks']['x']['cached'])
            self.assertEqual(hits,[1])

    def test_persistent_lesson_requires_explicit_approval(self):
        with tempfile.TemporaryDirectory() as d:
            mem=LessonMemory(Path(d)/'memory.sqlite')
            with self.assertRaises(PermissionError):
                mem.remember('marketing','Never invent a quote',['TEST-01'],approved=False)
            mem.remember('marketing','Never invent a quote',['TEST-01'],approved=True)
            self.assertEqual(len(mem.recall('marketing')),1)
            self.assertEqual(len(mem.recall('unrelated')),0)

    def test_validation_gate_failure_prevents_false_completion(self):
        e=ForgeRuntime()
        t=task('qa',tool='local.assert_contains',params={'text':'Alpha','fragments':['Alpha','Beta']},checks={'require_passed':True})
        r=e.run(mission(t),execute=True)
        self.assertEqual(r['status'],'FAILED')
        self.assertIn('Beta',str(r['tasks']['qa']['issues']))

    def test_success_receipt_validates_as_cor_result(self):
        from validate_payload import validate_result
        result=ForgeRuntime().run(mission(task('x')),execute=True)
        self.assertEqual(validate_result(result['tasks']['x']), [])

    def test_upstream_change_invalidates_task_cache(self):
        with tempfile.TemporaryDirectory() as d:
            store=Path(d)/'state.sqlite'
            hits=[]
            engine=ForgeRuntime(state_db=store)
            engine.register('internal.count', lambda p,u,f: hits.append(1) or {'message':p['message']})
            engine.run(mission(task('x',tool='internal.count',params={'message':'first'})),execute=True)
            engine.run(mission(task('x',tool='internal.count',params={'message':'second'})),execute=True)
            self.assertEqual(len(hits),2)

    def test_read_capability_respects_contract_denial(self):
        t=task('x',tool='local.extract_fields',params={'data':{'x':1},'fields':['x']},checks={'required_keys':['x']})
        t['contract']['permissions']['read']=False
        r=ForgeRuntime().run(mission(t),execute=True)
        self.assertEqual(r['status'],'BLOCKED')

    def test_external_effect_is_never_retried_automatically(self):
        attempts=[]
        engine=ForgeRuntime(grants={'TEST-01:publish:external.publish'})
        engine.register('external.publish',lambda p,u,f: attempts.append(1) or {},capability='external_write')
        t=task('publish',tool='external.publish',checks={'required_keys':['confirmed']},revisions=3)
        t['contract']['permissions']['require_approval']=['external_write']
        r=engine.run(mission(t),execute=True)
        self.assertEqual(r['status'],'FAILED')
        self.assertEqual(len(attempts),1)


if __name__ == '__main__':
    unittest.main()
