/* Nümtema Synapse — same-origin public MCP diagnostic; never sends secrets. */
(() => {
  'use strict';
  const base = location.origin;
  const meta = {
    'io.modelcontextprotocol/protocolVersion': '2026-07-28',
    'io.modelcontextprotocol/clientInfo': { name: 'synapse-public-dashboard', version: '0.4.2' },
    'io.modelcontextprotocol/clientCapabilities': {}
  };
  const publicNames = new Set([
    'numtema.list_agents', 'numtema.validate_cor',
    'numtema.compile_blueprint', 'numtema.plan_workflow'
  ]);
  const $ = (id) => document.getElementById(id);
  const rpc = (method, extra = {}) => ({
    jsonrpc: '2.0', id: 1, method, params: { _meta: meta, ...extra }
  });
  async function postRPC(payload) {
    const r = await fetch('/mcp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      cache: 'no-store'
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  }
  async function updateHealth() {
    try {
      const r = await fetch('/health', { cache: 'no-store' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const body = await r.json();
      if (body.status !== 'healthy' || body.execution_allowed !== false || body.public_tools !== 4)
        throw new Error('Configuration inattendue');
      $('health-status').textContent = 'Opérationnel';
      $('health-dot').classList.remove('checking', 'offline');
    } catch (_) {
      $('health-status').textContent = 'Non confirmé';
      $('health-dot').classList.remove('checking');
      $('health-dot').classList.add('offline');
    }
  }
  const examples = {
    http: () => `curl -X POST ${base}/mcp \\\n  -H 'Content-Type: application/json' \\\n  -d '${JSON.stringify(rpc('tools/list'))}'`,
    sse: () => `# Flux SSE historique, sans authentification\ncurl -N -H 'Accept: text/event-stream' \\\n  '${base}/sse'\n\n# Envoyer ensuite les messages JSON-RPC à\n# /messages?session_id=<id reçu dans le flux>`
  };
  let currentExample = 'http';
  function showExample(name) {
    currentExample = name;
    $('request-snippet').textContent = examples[name]();
    for (const btn of document.querySelectorAll('[data-example]')) {
      const active = btn.dataset.example === name;
      btn.classList.toggle('active', active);
      btn.setAttribute('aria-pressed', String(active));
    }
  }
  let toastTimer;
  function toast(message) {
    const node = $('toast');
    node.textContent = message;
    node.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => node.classList.remove('show'), 2300);
  }
  async function copy(text) {
    try {
      await navigator.clipboard.writeText(text);
      toast('Copié dans le presse-papiers');
    } catch (_) {
      toast('Copie indisponible dans ce navigateur');
    }
  }
  for (const btn of document.querySelectorAll('[data-copy]')) {
    btn.addEventListener('click', () => copy(base + btn.dataset.copy));
  }
  for (const btn of document.querySelectorAll('[data-example]')) {
    btn.addEventListener('click', () => showExample(btn.dataset.example));
  }
  $('copy-example').addEventListener('click', () => copy(examples[currentExample]()));
  async function diagnose() {
    const button = $('run-diagnostics');
    const display = $('diagnostic-result');
    button.disabled = true;
    display.className = 'diagnostic-result pending';
    display.textContent = 'Vérification des outils MCP et des restrictions…';
    try {
      const result = await postRPC(rpc('tools/list'));
      const tools = result?.result?.tools;
      if (!Array.isArray(tools)) throw new Error('Réponse MCP invalide');
      const names = new Set(tools.map(t => t.name));
      if (names.size !== 4 || [...publicNames].some(name => !names.has(name)))
        throw new Error(`Catalogue inattendu : ${[...names].join(', ')}`);
      const execution = await postRPC(rpc('tools/call', {
        name: 'numtema.execute_workflow', arguments: { mission: {} }
      }));
      const memory = await postRPC(rpc('tools/call', {
        name: 'numtema.recall_lessons', arguments: { scope: 'public-check' }
      }));
      if (!execution.error || !memory.error)
        throw new Error('Une opération privée a été acceptée');
      display.className = 'diagnostic-result ok';
      display.textContent = '✓ 4 outils publics confirmés · Exécution et mémoire interdites · Accès anonyme opérationnel.';
      updateHealth();
    } catch (e) {
      display.className = 'diagnostic-result failed';
      display.textContent = `Échec du diagnostic : ${e.message}`;
    } finally {
      button.disabled = false;
    }
  }
  $('run-diagnostics').addEventListener('click', diagnose);
  showExample('http');
  updateHealth();
})();
