"""Private Cognitive Memory v0.8: approved evidence, scope, retention and non-public usage."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from reflexion_engine import fingerprint
from llm_runtime import PrivateAgentRuntime


def report_for(output=None):
    output = output or {'text':'HERO sobre. CTA : Réserver.'}
    return {'mission_id':'TEST-LESSON-8', 'status':'COMPLETED',
            'tasks': {'draft':{'status':'COMPLETED', 'output':output,
                              'validation':{'mandatory_passed':True}}},
            'reflexion': {'draft':[{'status':'PASSED','candidate_sha256':fingerprint(output),
                                   'issues':[], 'suggestions':[]}]}}


class FakeBackend:
    def __init__(self):self.messages=[]
    def complete(self,messages,*,model,max_output_tokens,timeout_seconds):
        self.messages.append(messages)
        return {'text':'HERO sobre. CTA : Réserver.'}


class CognitiveMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'private'/'lessons.sqlite'

    def test_never_creates_storage_implicitly(self):
        from cognitive_memory import CognitiveMemory
        self.assertFalse(self.path.exists())
        with self.assertRaises(FileNotFoundError):CognitiveMemory(self.path,create=False)
        self.assertFalse(self.path.exists())

    def test_approval_requires_operator_and_verified_reflexion(self):
        from cognitive_memory import CognitiveMemory
        store=CognitiveMemory(self.path,create=True)
        with self.assertRaises(PermissionError):
            store.approve('alpha','Limiter les promesses',report_for(),'draft',operator_reviewed=False)
        invalid=report_for();invalid['reflexion']['draft'][0]['status']='REJECTED'
        with self.assertRaises(ValueError):
            store.approve('alpha','Limiter les promesses',invalid,'draft',operator_reviewed=True)
        invalid=report_for();invalid['reflexion']['draft'][0]['candidate_sha256']='0'*64
        with self.assertRaises(ValueError):
            store.approve('alpha','Limiter les promesses',invalid,'draft',operator_reviewed=True)
        self.assertEqual(store.recall('alpha'),[])

    def test_scoped_recall_is_exact_and_does_not_store_raw_candidate(self):
        from cognitive_memory import CognitiveMemory
        store=CognitiveMemory(self.path,create=True)
        ident=store.approve('client-A','Éviter les témoignages inventés',report_for(), 'draft',operator_reviewed=True)
        self.assertEqual(len(store.recall('client-A')),1)
        self.assertEqual(store.recall('client-B'),[])
        item=store.recall('client-A')[0]
        self.assertEqual(item['id'],ident)
        self.assertNotIn('HERO sobre',self.path.read_bytes().decode('utf-8','ignore'))
        self.assertEqual(item['evidence']['mission_id'],'TEST-LESSON-8')
        self.assertNotIn('output',item)
        self.assertEqual(len(store.recall('client-A')),1)
        self.assertEqual(store.approve('client-A','Éviter les témoignages inventés',report_for(),'draft',operator_reviewed=True),ident)

    def test_ttl_expiration_and_purge(self):
        from cognitive_memory import CognitiveMemory
        now=datetime(2026,10,30,tzinfo=timezone.utc)
        store=CognitiveMemory(self.path,create=True,clock=lambda:now)
        store.approve('scope','Leçon',report_for(),'draft',operator_reviewed=True,retention_days=1)
        self.assertEqual(len(store.recall('scope')),1)
        store.clock=lambda: now+timedelta(days=2)
        self.assertEqual(store.recall('scope'),[])
        self.assertEqual(store.purge_expired(),1)
        self.assertEqual(store.purge_expired(),0)

    def test_scope_purge_delete_and_invalid_limits(self):
        from cognitive_memory import CognitiveMemory
        store=CognitiveMemory(self.path,create=True)
        a=store.approve('a','Leçon A',report_for(),'draft',operator_reviewed=True)
        store.approve('b','Leçon B',report_for(),'draft',operator_reviewed=True)
        with self.assertRaises(ValueError):store.approve('a','Bad',report_for(),'draft',operator_reviewed=True,retention_days=9999)
        self.assertFalse(store.delete('b',a))
        self.assertTrue(store.delete('a',a))
        self.assertEqual(len(store.recall('b')),1)
        self.assertEqual(store.purge_scope('b'),1)
        self.assertEqual(store.recall('b'),[])

    def test_private_file_permissions_and_symlink_rejected(self):
        from cognitive_memory import CognitiveMemory
        store=CognitiveMemory(self.path,create=True)
        if os.name=='posix': self.assertEqual(self.path.stat().st_mode & 0o077,0)
        alt=Path(self.tmp.name)/'link.sqlite'
        alt.symlink_to(self.path)
        with self.assertRaises(ValueError):CognitiveMemory(alt,create=False)

    def test_worker_opened_db_is_strictly_read_only(self):
        from cognitive_memory import CognitiveMemory
        writer=CognitiveMemory(self.path,create=True)
        writer.approve('project','Leçon initiale',report_for(),'draft',operator_reviewed=True)
        reader=CognitiveMemory(self.path,create=False)
        self.assertEqual(len(reader.recall('project')),1)
        with self.assertRaises(PermissionError):
            reader.approve('project','Modification interdite',report_for(),'draft',operator_reviewed=True)
        with self.assertRaises(PermissionError):
            reader.purge_scope('project')
        self.assertEqual(len(writer.recall('project')),1)

    def test_private_worker_retrieves_only_selected_scope_and_never_writes_memory(self):
        from cognitive_memory import CognitiveMemory
        store=CognitiveMemory(self.path,create=True)
        store.approve('project-one','Préférer les promesses vérifiables',report_for(),'draft',operator_reviewed=True)
        store.approve('project-two','SECRET AUTRE PROJET',report_for(),'draft',operator_reviewed=True)
        backend=FakeBackend()
        runtime=PrivateAgentRuntime(backend,model='local-test',memory=store,memory_scope='project-one',memory_limit=5)
        mission={'mission_id':'TASK08','steps':[{'id':'draft','agent_id':'Rhetorica','tool':'llm.draft',
                 'objective':'Écrire HERO et CTA','expected_keys':['text'],
                 'checks':{'required_keys':['text']},'max_revisions':0}]}
        result=runtime.run(mission,execute=True)
        self.assertEqual(result['status'],'COMPLETED')
        prompt=json.dumps(backend.messages,ensure_ascii=False)
        self.assertIn('Préférer les promesses vérifiables',prompt)
        self.assertNotIn('SECRET AUTRE PROJET',prompt)
        self.assertEqual(len(store.recall('project-one')),1)
        self.assertEqual(len(store.recall('project-two')),1)

    def test_memory_not_recalled_on_dry_run(self):
        from cognitive_memory import CognitiveMemory
        store=CognitiveMemory(self.path,create=True)
        backend=FakeBackend(); runtime=PrivateAgentRuntime(backend,model='local-test',memory=store,memory_scope='scope')
        mission={'mission_id':'TASK08','steps':[{'id':'draft','agent_id':'Rhetorica','tool':'llm.draft',
                 'objective':'Texte','expected_keys':['text'],'checks':{'required_keys':['text']}}]}
        result=runtime.run(mission,execute=False)
        self.assertEqual(result['status'],'PLANNED')
        self.assertEqual(backend.messages,[])

    def test_anonymous_http_facade_does_not_register_memory_tools(self):
        from public_mcp_policy import PublicSynapseMCPServer, PUBLIC_TOOL_NAMES
        self.assertEqual(len(PUBLIC_TOOL_NAMES),4)
        self.assertFalse(any('memory' in name or 'lesson' in name for name in PUBLIC_TOOL_NAMES))
        server=PublicSynapseMCPServer()
        result=server.handle({'jsonrpc':'2.0','id':1,'method':'tools/call',
                              'params':{'name':'numtema.recall_lessons','arguments':{'scope':'a'}}})
        self.assertIn('error',result)
        result=server.handle({'jsonrpc':'2.0','id':2,'method':'tools/call',
                              'params':{'name':'numtema.approve_lesson','arguments':{}}})
        self.assertIn('error',result)

    def test_cli_requires_confirmation_for_destructive_scope_purge(self):
        from cognitive_memory import CognitiveMemory
        store=CognitiveMemory(self.path,create=True)
        store.approve('scope','Exemple',report_for(),'draft',operator_reviewed=True)
        base=[sys.executable,str(SCRIPTS/'memory_cli.py'),'--db',str(self.path)]
        attempt=subprocess.run(base+['purge-scope','--scope','scope'],capture_output=True,text=True)
        self.assertNotEqual(attempt.returncode,0)
        self.assertEqual(len(store.recall('scope')),1)

    def test_cli_operator_lifecycle(self):
        script=SCRIPTS/'memory_cli.py'
        report=Path(self.tmp.name)/'report.json'
        report.write_text(json.dumps(report_for()),encoding='utf-8')
        base=[sys.executable,str(script),'--db',str(self.path)]
        cmd=base+['approve','--report',str(report),'--task-id','draft','--scope','project',
                  '--insight','Préférer les preuves vérifiables','--operator-reviewed']
        p=subprocess.run(cmd,capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        result=subprocess.run(base+['recall','--scope','project'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(len(json.loads(result.stdout)['lessons']),1)
        purge=subprocess.run(base+['purge-scope','--scope','project','--confirm'],capture_output=True,text=True)
        self.assertEqual(purge.returncode,0,purge.stderr)
        self.assertEqual(len(json.loads(subprocess.run(base+['recall','--scope','project'],capture_output=True,text=True).stdout)['lessons']),0)

if __name__ == '__main__':unittest.main()
