# Nümtema Synapse Cognitive OS — Public MCP v0.4.1

**Serveur MCP anonyme** pour préparation et validation de workflows CoR, RRLA, Reflexion et Agent Forge. Code source public ; les ressources privées du plugin ChatGPT ne sont pas publiées ici.

## API publique sans authentification

- `GET /mcp` : page de présentation limitée aux **4 outils publics**.
- `POST /mcp`, `POST /jsonrpc` : JSON-RPC MCP HTTP.
- `GET /sse` puis `POST /messages?session_id=...` : transport SSE historique conservé.
- `GET /health` : santé et indication `execution_allowed: false`.

Outils acceptés : `numtema.list_agents`, `numtema.validate_cor`, `numtema.compile_blueprint`, `numtema.plan_workflow`.

**Interdits sur TOUS les transports publics :** `numtema.execute_workflow`, `numtema.recall_lessons`, toute écriture sur une base SQLite, les accès aux comptes et les opérations externes. Les identifiants, jetons et faux en-têtes client ne créent aucune permission. Le serveur local `mcp_server.py` garde ses six outils dans un environnement de confiance, distinct du serveur HTTP public.

## Exécuter localement

```bash
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s skills/numtema-synapse/tests -v
docker compose up --build -d
curl http://127.0.0.1:8000/health
```

`Dockerfile` lance `mcp_http_server.py`. Dans Compose, le port est lié à `127.0.0.1` pour éviter d'exposer directement le HTTP non chiffré. Pour Coolify, configurer un domaine HTTPS pointant vers le port interne 8000 et redéployer volontairement la révision voulue.

## Sécurité et limites

- Aucune authentification utilisateur, aucun mot de passe, aucun Bearer, aucun OAuth.
- Les en-têtes `Origin` sont rejetés par défaut. Pour autoriser un navigateur sur un domaine de confiance, configurer `SYNAPSE_ALLOWED_ORIGINS=https://exemple.fr` (origines HTTPS exactes, séparées par des virgules).
- Taille maximale de requête : 1 Mo ; 32 connexions SSE simultanées ; 16 réponses en file par session ; 60 appels/minute par processus par défaut. Mettre aussi un plafond de débit au reverse proxy : les limites applicatives ne remplacent pas une protection réseau.
- **Service public : ne jamais envoyer de secrets ou de données client confidentielles.** L'absence d'authentification interdit d'isoler correctement des locataires.
- Les variables historiques `SYNAPSE_ALLOW_EXECUTE`, `SYNAPSE_STATE_DB` et `SYNAPSE_LESSONS_DB` n'activent rien dans le serveur HTTP public.
- Les tests locaux ne prouvent pas que Coolify a déjà redéployé ni que chaque client MCP externe est compatible.

## Vérification avant production

Contrôler la liste exacte des quatre outils depuis `/mcp` et via SSE ; tenter des appels à `execute_workflow` et `recall_lessons` et obtenir un refus ; vérifier l'accès anonyme, l'origine rejetée, le volume des requêtes et les journaux proxy. Ne pas redéployer automatiquement depuis cette PR sans validation de l'instance Coolify existante.

Voir `skills/numtema-synapse/SKILL.md` et les références pour l'architecture cognitive générale.

## Dashboard web Synapse v0.4.2

La route **GET /mcp** propose une interface Nümtema responsive (desktop et mobile) avec architecture CoR, registre des quatre outils publics, exemples HTTP/SSE et diagnostic interactif. Les assets locaux sont servis par `GET /assets/synapse.css` et `GET /assets/synapse.js` ; aucun CDN ni police distante. Les ressources sont protégées par une CSP restrictive.

Le bouton « Tester la passerelle » réalise réellement `tools/list` et vérifie le refus des deux opérations sensibles, mais **n'exécute jamais** de workflow. Le contrôle `Origin` accepte les appels du même domaine et rejette les origines tierces non autorisées. Aucun login ou token demandé.

Tests locaux : `python3 -m unittest discover -s skills/numtema-synapse/tests -q`. Une vérification locale ne remplace pas les contrôles sur le déploiement Coolify ; valider la version, les quatre outils et les refus après déploiement.

## Mission Studio v0.5.0 — Préparer sans exécuter

Le dashboard `GET /mcp` accueille désormais **Mission Studio** : formulaire guidé, presets conversion/cadrage/éditorial, compilation de trois contrats CoR 2.0 par `numtema.compile_blueprint`, contrôle DAG via `numtema.plan_workflow`, validation de chaque contrat via `numtema.validate_cor`, visualisation interactive et export de `mission.json` et `blueprint.json`. Les trois outils sont les appels MCP existants ; il ne s'agit pas d'une simulation visuelle.

**Sans login ni jeton.** Aucun worker IA n'est lancé, aucune action externe, pas de mémoire persistante. Le formulaire soumet des données à une API publique anonyme : ne jamais saisir de secrets ou de données clients confidentielles. Les exports sont réalisés côté navigateur. Les profils des agents décrivent des rôles, pas des processus LLM autonomes.

Tests : `python3 -m unittest discover -s skills/numtema-synapse/tests -q` (100 tests locaux), puis `SYNAPSE_TEST_URL=http://127.0.0.1:8000 node skills/numtema-synapse/tests/node_mission_studio_integration.js` avec serveur local démarré. Un contrôle visuel en navigateur reste nécessaire sur Coolify (environnement actuel : Chromium bloqué par la politique réseau).

## v0.6.0 — Agent Runtime IA privé, sans authentification du Studio

Mission Studio peut maintenant compiler un blueprint **à destination d'Ollama** via l'option « Préparer pour un agent IA local ». L'API publique n'exécute aucun modèle : elle accepte la **planification** `llm.draft`, mais refuse toujours les invocations d'exécution et d'accès SQLite.

Le worker privé `skills/numtema-synapse/scripts/llm_runtime.py` utilise réellement `POST /api/chat` lorsque l'opérateur lance la commande locale avec `--execute` et qu'Ollama est disponible. Les appels et révisions sont bornés ; aucun stockage persistant ni action externe par le modèle. Une mission terminée est **structurellement** validée, pas factuellement certifiée.

```bash
python3 skills/numtema-synapse/scripts/llm_runtime.py \
  skills/numtema-synapse/examples/blueprint-local-llm.json --model gemma3:1b
# Dry-run PLANNED. Après installation et démarrage d'Ollama :
python3 skills/numtema-synapse/scripts/llm_runtime.py \
  skills/numtema-synapse/examples/blueprint-local-llm.json --model gemma3:1b --execute
```

**Le worker ne doit jamais être relié à un endpoint HTTP public sans authentification.** Il s'exécute depuis une machine ou un réseau de confiance, hors de la passerelle actuelle Coolify. Voir [le guide du runtime](skills/numtema-synapse/references/llm-runtime-v06.md). Les tests de bout en bout utilisent un serveur Ollama simulé, pas un modèle installé ; valider localement avec un vrai modèle avant tout usage réel.

## Reflexion Engine v0.7.0 — Validation heuristique privée

Le worker Ollama accepte `--reflexion` pour soumettre chaque brouillon à une **double validation** : les contrôles structurels CoR, puis une revue LLM séparée (`--reviewer-model` facultatif, pour choisir un autre modèle local). En cas de rejet, les défauts sont réinjectés dans une révision bornée. Le reçu contient l'empreinte SHA-256 du candidat et le verdict, jamais le brouillon complet.

```bash
# Planification : aucun modèle sollicité
python3 skills/numtema-synapse/scripts/llm_runtime.py skills/numtema-synapse/examples/blueprint-local-llm.json --model gemma3:1b --reflexion
# Sur un hôte privé où Ollama et le(s) modèle(s) sont réellement installés :
python3 skills/numtema-synapse/scripts/llm_runtime.py skills/numtema-synapse/examples/blueprint-local-llm.json --model gemma3:1b --reflexion --execute
```

**L'évaluation est heuristique, jamais une vérification factuelle ou une garantie de conformité.** Un reviewer malformé refuse la validation. Le mode sans `--reflexion` conserve le comportement v0.6. Le serveur public anonyme reste limité aux quatre outils planificateurs, sans worker ni lecture SQLite. Voir [la documentation Reflexion](skills/numtema-synapse/references/reflexion-v07.md).

**Preuves disponibles :** 123 tests Python locaux, plus test CLI HTTP contre simulateur Ollama ; aucun modèle Ollama réel n'était accessible dans cette session. Validation de production et de vrai modèle encore requise.
