#!/usr/bin/env python3
"""Agent Forge: compile a declared mission blueprint into verifiable CoR contracts.

This compiler does NOT use an LLM, autonomously choose tools, grant permissions,
or run code. The host is responsible for adapter registration and approvals.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from validate_payload import validate_contract

SENSITIVE={'external_write','financial_spend','deployment'}


class AgentForge:
    def compile(self, blueprint: dict) -> dict:
        if not isinstance(blueprint,dict) or not isinstance(blueprint.get('mission_id'),str) or not blueprint['mission_id']:
            raise ValueError('Mission blueprint requires mission_id')
        steps=blueprint.get('steps')
        if not isinstance(steps,list) or not steps:
            raise ValueError('Mission blueprint requires nonempty steps')
        context=blueprint.get('context', {})
        if not isinstance(context,dict):
            raise ValueError('context must be object')
        tasks=[]
        for step in steps:
            if not isinstance(step,dict):
                raise ValueError('step must be object')
            for key in ('id','agent_id','objective','tool'):
                if not isinstance(step.get(key),str) or not step[key].strip():
                    raise ValueError('step requires '+key)
            if any(step.get('permissions',{}).get(x) is True for x in SENSITIVE):
                raise ValueError('Blueprint cannot grant external writes, deployments or spending')
            cap=step.get('capability','draft')
            if cap not in ('read','draft',*SENSITIVE):
                raise ValueError('Unknown capability')
            max_revisions=step.get('max_revisions',1)
            if type(max_revisions) is not int or not 0<=max_revisions<=5:
                raise ValueError('max_revisions must be integer 0..5')
            expected=step.get('expected_keys',['message'])
            checks=step.get('checks',{'required_keys':expected})
            if not isinstance(checks,dict):
                raise ValueError('checks must be object')
            permissions={'read':True,'draft':True,'external_write':False,'financial_spend':False,
                         'deployment':False,'requested_tools':[step['tool']],
                         'require_approval':[cap] if cap in SENSITIVE else []}
            contract={
              'version':'2.0', 'contract_id':f"{blueprint['mission_id']}:{step['id']}",
              'identity':{'agent_id':step['agent_id'],'role':step.get('role',step['agent_id']),
                          'supervisor':'synapse_orchestrator'},
              'mission':{'objective':step['objective'], 'expected_outcome':step.get('expected_outcome', 'Validated task artifact')},
              'context':context,
              'inputs':{'required':step.get('required_inputs',[]),'optional':step.get('optional_inputs',[])},
              'scope':{'allowed_tasks':[step['objective']], 'excluded_tasks':step.get('excluded_tasks',[])},
              'tools':{'allowlist':[step['tool']]},
              'permissions':permissions,
              'deliverables':{'format':'structured_json','required':expected},
              'validation':{'mandatory_checks':step.get('mandatory_checks',['task_checks'])},
              'handoff':{'destination':'synapse_orchestrator','include':['deliverables','validation_report']},
              'reflection':{'enabled':True,'max_revisions':max_revisions},
              'termination':{'success':'All task checks pass', 'blocked':'Missing inputs or permission',
                             'failed':'Bounded retries exhausted','approval_required':'Sensitive action pending host grant'}
            }
            errors=validate_contract(contract)
            if errors:
                raise ValueError('; '.join(errors))
            tasks.append({'id':step['id'],'contract':contract,'tool':step['tool'],
                          'depends_on':step.get('depends_on',[]),'params':step.get('params',{}),
                          'checks':checks})
        return {'version':'0.2.0','mission_id':blueprint['mission_id'],'tasks':tasks}


def main():
    parser=argparse.ArgumentParser(description='Compile a mission blueprint to CoR task DAG')
    parser.add_argument('blueprint',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    source=json.loads(args.blueprint.read_text(encoding='utf-8'))
    result=AgentForge().compile(source)
    output=json.dumps(result,ensure_ascii=False,indent=2)
    if args.output:
        args.output.write_text(output+'\n',encoding='utf-8')
        print(args.output)
    else:
        print(output)

if __name__ == '__main__':
    main()
