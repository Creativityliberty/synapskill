import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'validate_payload.py'

spec = importlib.util.spec_from_file_location('validate_payload', SCRIPT)
module = importlib.util.module_from_spec(spec)
if spec.loader:
    spec.loader.exec_module(module)


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.good = json.loads((ROOT / 'examples' / 'cor-landing-page.json').read_text(encoding='utf-8'))

    def test_accepts_complete_contract(self):
        self.assertEqual(module.validate_contract(self.good), [])

    def test_rejects_missing_mission(self):
        item = dict(self.good)
        item.pop('mission')
        self.assertTrue(any('mission' in x for x in module.validate_contract(item)))

    def test_rejects_undeclared_tool(self):
        item = json.loads(json.dumps(self.good))
        item['permissions']['requested_tools'] = ['knowledge_retrieval', 'deploy_production']
        self.assertTrue(any('deploy_production' in x for x in module.validate_contract(item)))

    def test_rejects_auto_spend(self):
        item = json.loads(json.dumps(self.good))
        item['permissions']['financial_spend'] = True
        self.assertTrue(any('financial_spend' in x for x in module.validate_contract(item)))

    def test_rejects_unbounded_retries(self):
        item = json.loads(json.dumps(self.good))
        item['reflection']['max_revisions'] = -1
        self.assertTrue(any('max_revisions' in x for x in module.validate_contract(item)))

    def test_rejects_invalid_state(self):
        result = {'contract_id': 'COR-001', 'status': 'MAGIC', 'deliverables': {}}
        self.assertTrue(module.validate_result(result))

    def test_accepts_result(self):
        result = {'contract_id':'COR-001','status':'COMPLETED','deliverables':{'page_outline':[]}, 'validation':{'mandatory_passed':True}, 'evidence':[]}
        self.assertEqual(module.validate_result(result), [])


if __name__ == '__main__':
    unittest.main()
