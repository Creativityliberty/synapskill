#!/usr/bin/env python3
"""Validation locale des formats Nümtema CoR v2.0 (sans réseau ni secrets)."""
import argparse
import json
from pathlib import Path

MANDATORY = (
    "version", "contract_id", "identity", "mission", "context", "inputs",
    "scope", "tools", "permissions", "deliverables", "validation", "handoff",
    "reflection", "termination"
)
STATES = {"DRAFT", "READY", "RUNNING", "REVIEW", "REVISION", "COMPLETED", "BLOCKED", "FAILED"}


def validate_contract(contract):
    if not isinstance(contract, dict):
        return ["contract: expected JSON object"]
    issues = [f"{field}: required" for field in MANDATORY if field not in contract]
    for field, sub in {
        "identity": ("agent_id", "supervisor", "role"),
        "mission": ("objective", "expected_outcome"),
        "tools": ("allowlist",),
        "deliverables": ("format", "required"),
        "validation": ("mandatory_checks",),
        "termination": ("success", "blocked", "failed", "approval_required")
    }.items():
        value = contract.get(field)
        if isinstance(value, dict):
            issues.extend(f"{field}.{key}: required" for key in sub if not value.get(key))
        elif field in contract:
            issues.append(f"{field}: expected object")
    tools = contract.get("tools") or {}
    permissions = contract.get("permissions") or {}
    if isinstance(tools, dict) and isinstance(permissions, dict):
        allow = tools.get("allowlist", [])
        requested = permissions.get("requested_tools", [])
        if not isinstance(allow, list) or not isinstance(requested, list):
            issues.append("permissions.requested_tools and tools.allowlist must be arrays")
        else:
            issues.extend(f"permissions.requested_tools: undeclared tool '{x}'" for x in requested if x not in allow)
        for operation in ("financial_spend", "deployment", "external_write"):
            if permissions.get(operation) is True:
                issues.append(f"permissions.{operation}: cannot be auto-authorized by a skill contract")
    reflection = contract.get("reflection") or {}
    if isinstance(reflection, dict):
        count = reflection.get("max_revisions")
        if not isinstance(count, int) or isinstance(count, bool) or not (0 <= count <= 5):
            issues.append("reflection.max_revisions: must be integer 0..5")
    else:
        issues.append("reflection: expected object")
    return issues


def validate_result(result):
    if not isinstance(result, dict):
        return ["result: expected JSON object"]
    issues = [f"{x}: required" for x in ("contract_id", "status", "deliverables") if x not in result]
    status = result.get("status")
    if status not in STATES:
        issues.append(f"status: invalid state {status!r}")
    if status == "COMPLETED":
        if not (isinstance(result.get("validation"), dict) and result["validation"].get("mandatory_passed") is True):
            issues.append("validation.mandatory_passed: required for COMPLETED")
        if not isinstance(result.get("evidence"), list):
            issues.append("evidence: required list for COMPLETED")
    return issues


def main():
    ap = argparse.ArgumentParser(description="Contrôle local d'un contrat CoR ou d'un résultat")
    ap.add_argument("json_file", type=Path)
    ap.add_argument("--kind", choices=("contract", "result"), default="contract")
    args = ap.parse_args()
    value = json.loads(args.json_file.read_text(encoding="utf-8"))
    problems = validate_contract(value) if args.kind == "contract" else validate_result(value)
    for p in problems:
        print("ERROR:", p)
    if not problems:
        print("VALID (structural/policy checks only; not factual verification)")
    return int(bool(problems))


if __name__ == "__main__":
    raise SystemExit(main())
