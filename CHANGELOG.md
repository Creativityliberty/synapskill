## v0.8.1 — Private Ollama Live Validation Kit (2026-10-30)

- Docker Compose bootstrap à sorties réseau temporaires, sans ports publiés, pour télécharger `gemma3:1b`.
- Stack Ollama + worker sur réseau Docker privé `internal: true` sans proxy ni ports.
- Worker déclenché manuellement : vérification `api/tags`, appel JSON Ollama et exécution CoR/Reflexion ; verdict GO/NO-GO minimal, fail-closed.
- Documentation Coolify/Docker et tests de non-exposition.
- Aucun modèle réel exécuté depuis cet environnement ; absence de Docker et de daemon Ollama signalée.
- Surface publique Mission Studio et MCP inchangée.

## v0.8.0 — Cognitive Memory privée (30 octobre 2026)
- Leçons compactes à preuve SHA-256 cohérente avec un rapport Reflexion, créées uniquement après validation explicite d'un opérateur.
- SQLite privé `0600`, lecture seule pour le worker, scope exact, expiration 1–365 jours, suppression unitaire / par projet / expirées.
- CLI opérateur séparée de la passerelle MCP publique ; aucune fonction de mémoire exposée au navigateur.
- Tests de sécurité et de régression : 135 tests Python réussis ; vrai modèle Ollama non testé.

## 0.7.0 — 2026-10-30
- Ajout de `reflexion_engine.py` : validateur strict de verdict critique, échec fermé et empreintes de candidats.
- Ajout des options CLI privées `--reflexion` et `--reviewer-model` pour activer une critique distincte, après les tests CoR déterministes et avant acceptation.
- Les défauts et suggestions sont réellement réinjectés dans la nouvelle tentative, avec budget d’appels et limites de révision.
- Aucun nouveau outil MCP public, aucun login, aucune exécution via HTTP/SSE, aucun stockage nouveau.
- Vérification locale avec serveur Ollama simulé ; test réel sur l’hôte Ollama restant nécessaire.

## 0.6.0 — 2026-10-30
- Introduit le worker privé `llm_runtime.py` : adaptateur Ollama via JSON POST `/api/chat`, sorties JSON structurées, budget par mission, vérification CoR, feedback Reflexion borné.
- Planification des tâches `llm.draft`/`llm.review` côté API publique sans les rendre exécutables ; maintient les 4 outils MCP publics et l'absence d'authentification.
- Option Studio « Préparer pour un agent IA local », blueprint exportable ; aucune exécution depuis le navigateur.
- Ajoute une mission fictive, un guide d'exploitation privé, des tests de protocole sur serveur local simulé. Pas de véritable modèle Ollama disponible dans l'environnement de test.

# Changelog

## v0.5.0 — Mission Studio public et planification (30 octobre 2026)
- Atelier guidé intégré au dashboard : briefs et presets, contrats CoR compilés, DAG visualisé, validation structurelle et export JSON.
- Utilise les trois outils MCP publics existants, sans aucun nouvel endpoint, aucune exécution ni mémoire serveur.
- Trois modèles non-IA : conversion, cadrage, éditorial. Les agents restent des rôles conceptuels.
- UI responsive sans CDN, sortie utilisateur affichée via textContent pour éviter l'injection HTML.
- Tests API/DOM et régression des garde-fous réseau.

## 0.4.2 - Premium public MCP dashboard

Responsive HTML/CSS/JS, same-origin diagnostics, 4-tool public policy, no authentication, no remote execute/lessons. Tests: 73 local. No hosted validation implied.


## v0.4.1 — Accès MCP public sans authentification (30 octobre 2026)
- Retrait complet du jeton Bearer et de la configuration de secrets sur la passerelle HTTP publique.
- Maintien d’une allowlist de quatre outils de préparation et des interdictions d’exécution/SQLite.
- Rate limit global réduit à 30 appels/minute/processus ; délai de socket borné.
- Nouveau probe anonyme et tests HTTP qui valident l’accès sans token et le refus des outils sensibles.
- Candidat local seulement : aucun changement effectué sur le serveur Coolify existant.

## v0.4.0 — Candidat HTTP sécurisé (30 octobre 2026)
- Passerelle MCP `POST /mcp` moderne avec Bearer via variable d'environnement (token obligatoire).
- Validation stricte des headers MCP, de la métadonnée de version et de l'en-tête `Origin` ; gestion des erreurs et limites de taille.
- Exposition réseau limitée à quatre outils read/draft ; `execute_workflow` et `recall_lessons` interdits à distance.
- Dockerfile de staging Coolify, exemple de secret, documentation de proxy TLS et probe distant en lecture seule.
- Tests de sécurité et véritables appels HTTP locaux ajoutés : 75 tests au total.
- **Aucun déploiement sur le domaine existant, aucune bascule `/sse`, aucun OAuth ni isolation multiclient**.

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
