"""Anonymous PUBLIC MCP policy. Applies to HTTP POST and legacy SSE alike.

All remote clients are untrusted. Access does not imply identity or capability grants.
The six-tool stdio server is deliberately distinct from this four-tool public facade.
"""
from __future__ import annotations

from mcp_server import SynapseMCPServer, rpc_error

PUBLIC_TOOL_NAMES = frozenset({
    'numtema.list_agents',
    'numtema.validate_cor',
    'numtema.compile_blueprint',
    'numtema.plan_workflow',
})


class PublicSynapseMCPServer(SynapseMCPServer):
    def __init__(self, *, max_calls_per_minute=60):
        super().__init__(allow_execute=False, state_db=None, lessons_db=None,
                         max_calls_per_minute=max_calls_per_minute)
        # Planning-only descriptors: the registered handlers are not remotely callable.
        # Public policy denies execute_workflow before MCP dispatch.
        def never_execute(*args, **kwargs):
            raise PermissionError('LLM execution is private-only')
        self.runtime.register('llm.draft', never_execute, capability='draft', version='plan-only-v06')
        self.runtime.register('llm.review', never_execute, capability='draft', version='plan-only-v06')

    def call_tool(self, name, args=None, *, modern=True):
        if name not in PUBLIC_TOOL_NAMES:
            raise KeyError('Unknown public tool')
        return super().call_tool(name, args, modern=modern)

    def handle(self, msg):
        # Deny *before* the underlying dispatcher, regardless of client metadata.
        if isinstance(msg, dict) and msg.get('method') == 'tools/call':
            params = msg.get('params')
            if isinstance(params, dict) and params.get('name') not in PUBLIC_TOOL_NAMES:
                return rpc_error(msg.get('id'), -32602, 'Unknown public tool')
        result = super().handle(msg)
        if isinstance(msg, dict) and isinstance(result, dict) and msg.get('method') == 'tools/list':
            listing = result.get('result')
            if isinstance(listing, dict) and isinstance(listing.get('tools'), list):
                listing['tools'] = [tool for tool in listing['tools']
                                    if tool.get('name') in PUBLIC_TOOL_NAMES]
        if isinstance(msg, dict) and isinstance(result, dict) and msg.get('method') == 'server/discover':
            discovery = result.get('result')
            if isinstance(discovery, dict):
                discovery['instructions'] = (
                    'Anonymous public planning and validation only. No execution, '
                    'private memory, account access, payments or publishing. '
                    'Do not submit confidential information.'
                )
        return result
