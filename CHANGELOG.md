## v0.6.0 — 2026-10-30
- Worker privé Ollama opt-in, contrats CoR et appels IA bornés avec feedback et contrôles déterministes.
- Mission Studio peut planifier un blueprint `llm.draft` sans exécution ni authentification publique.
- 114 tests locaux réussis (dont CLI + serveur Ollama simulé), test avec modèle installé encore requis.

## v0.5.0 — Mission Studio (30 octobre 2026)
- Création de mission guidée, contrats CoR compilés et validés, DAG vérifié et exports JSON sans exécution distante.
- Extension du dashboard existant, trois presets, interface responsive, tests API/DOM et intégration Node.
- Aucune authentification, aucune connexion à un LLM, aucune donnée conservée côté serveur.

# Versions

## 0.3.0 — Serveur MCP stdio local dual-era

- MCP stdio JSON-RPC : `server/discover` (2026), `initialize` (2025), `tools/list`, `tools/call`, `ping`.
- Six outils MCP liés au véritable Agent Forge/Forge Runtime, sans LLM autonome ni connecteurs externes.
- Exécution locale désactivée par défaut, activation explicite par option d’hôte.
- Validation d’entrée, refus des permissions forgées, garde taille/débit et schéma des checks.
- Tests de transport en sous-processus avec stdin/stdout et régression des fonctions v0.2.
- Aucun service ou compte externe connecté ; pas de serveur HTTP.


## 0.2.0 — Agent Forge et runtime local

- Ajout du compilateur `AgentForge` : blueprint déclaré → contrats CoR 2.0 par étape.
- Ajout du moteur `ForgeRuntime` : DAG, ordre topologique, permission CoR, approbation hôte pour outils sensibles, contrôles déterministes et révisions Reflexion bornées.
- Ajout de la mémoire opt-in SQLite : événements, cache des tâches validées, leçons avec preuve et consentement du code hôte.
- Ajout des reçus de mission et d'une démonstration entièrement fictive exécutable hors ligne.
- Ajout de tests de sécurité et de comportement, y compris l'interdiction des retries automatiques d'actions sensibles.
- Aucune connexion ou publication externe n'a été effectuée.

## 0.1.0 — Skill principal

- Contrats CoR 2.0, registre des agents, RRLA, Reflexion, Morphius, Vortex, buffers, U₀, commandes conversationnelles.
- Validation structurelle initiale des contrats/résultats.
