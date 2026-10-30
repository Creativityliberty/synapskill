# Nümtema Synapse Cognitive OS — v0.8.1

**Tests sur une machine neuve :** `python3 -m pip install -r requirements-test.txt` puis `python3 -m unittest discover -s skills/numtema-synapse/tests -q`. La validation Docker Compose reste distincte et requiert Docker sur le serveur privé.

**Nouveau : kit reproductible pour valider une vraie inférence Ollama + CoR + Reflexion sur un hôte privé.** Aucun changement des quatre outils MCP publics, aucune authentification utilisateur ajoutée, aucune exécution distante publique. Voir [`private-ollama-validation-v081.md`](skills/numtema-synapse/references/private-ollama-validation-v081.md).

Le kit comprend une pile Docker isolée sans port publié, une phase distincte de téléchargement du modèle, un worker déclenché manuellement et un rapport GO/NO-GO sans contenu de mission. Aucun modèle n'a été exécuté sur l'infrastructure Coolify depuis l'environnement de préparation : cette version facilite **une validation à réaliser**, elle ne la revendique pas comme accomplie.

```bash
# Depuis la racine du dépôt sur le serveur Docker privé
docker compose -f deployment/ollama-bootstrap.compose.yml up -d ollama
docker compose -f deployment/ollama-bootstrap.compose.yml exec -T ollama ollama pull gemma3:1b
docker compose -f deployment/ollama-bootstrap.compose.yml down
docker compose -f deployment/ollama-private.compose.yml up -d ollama
docker compose -f deployment/ollama-private.compose.yml run --rm -T worker > /tmp/synapse-private-e2e.json
cat /tmp/synapse-private-e2e.json
```

# Nümtema Synapse Cognitive OS — v0.8.0

**v0.8 — Cognitive Memory privée et contrôlée :** leçons produites à partir de rapports CoR/Reflexion terminés et **approuvées manuellement** par un opérateur, SQLite avec rétention bornée, lecture limitée à une portée de projet et purge explicite. Le worker ouvre la mémoire en lecture seule, sans écriture automatique. La passerelle publique anonyme conserve exactement ses quatre outils de préparation, sans mémoire ni exécution LLM. Référence : [Cognitive Memory v0.8](skills/numtema-synapse/references/cognitive-memory-v08.md).

```bash
# Tests
python3 -m unittest discover -s skills/numtema-synapse/tests -q
# Lecture depuis une DB existante ; jamais créée implicitement par le worker
python3 skills/numtema-synapse/scripts/memory_cli.py --db ./state/cognitive-private.sqlite recall --scope projet-demo
```

**Important :** approbation humaine ≠ certification de vérité. Aucune instance Ollama réelle n'était accessible dans l'environnement de développement ; le prochain test opérationnel doit s'effectuer sur l'hôte privé équipé du modèle.

# Nümtema Synapse Cognitive OS — v0.7.0

**v0.7 : Reflexion Engine privé (opt-in).** Après la génération d’un brouillon, Synapse impose les contrôles déterministes du contrat puis, si activé, un second appel LLM de critique. Une critique négative ou malformée bloque le livrable et réinjecte des corrections dans les tentatives restantes. Ce contrôle reste **heuristique**, pas une certification factuelle. L’interface MCP publique ne change pas et ne permet aucun appel LLM.

```bash
python3 -m unittest discover -s skills/numtema-synapse/tests -q
python3 skills/numtema-synapse/scripts/llm_runtime.py skills/numtema-synapse/examples/blueprint-local-llm.json --model gemma3:1b --reflexion
# Sur un hôte privé avec Ollama démarré, après installation du modèle :
python3 skills/numtema-synapse/scripts/llm_runtime.py skills/numtema-synapse/examples/blueprint-local-llm.json --model gemma3:1b --reflexion --execute
```

Référence complète : [Reflexion v0.7](skills/numtema-synapse/references/reflexion-v07.md). **Le test avec un véritable modèle Ollama sur Coolify n’a pas été réalisé depuis cet environnement.**

## Ancien runtime v0.6

**Nouveauté : worker IA privé Ollama et préparation de tâches IA dans Mission Studio.** Le serveur MCP public reste anonyme, avec quatre outils de préparation uniquement. La vraie génération LLM se fait hors HTTP public : l'opérateur lance le worker CLI `llm_runtime.py --execute` sur une machine disposant d'Ollama. Aucun worker autonome n'est hébergé par ChatGPT et aucun modèle n'est fourni dans l'archive.

Voir [le guide v0.6](skills/numtema-synapse/references/llm-runtime-v06.md) et l'exemple [`blueprint-local-llm.json`](skills/numtema-synapse/examples/blueprint-local-llm.json).

```bash
python3 -m unittest discover -s skills/numtema-synapse/tests -q
python3 skills/numtema-synapse/scripts/llm_runtime.py skills/numtema-synapse/examples/blueprint-local-llm.json --model gemma3:1b
# Si Ollama est bien installé, lancé et que le modèle est présent :
python3 skills/numtema-synapse/scripts/llm_runtime.py skills/numtema-synapse/examples/blueprint-local-llm.json --model gemma3:1b --execute
```

## Version précédente (v0.5)

# Nümtema Synapse Cognitive OS — v0.6.0

## Mission Studio — nouvel atelier public (v0.5.0)

La page `GET /mcp` inclut Mission Studio : trois modèles de mission (landing page, cadrage stratégique, plan éditorial), brief guidé, compilation de trois contrats CoR 2.0, planification DAG et validation structurale par `numtema.validate_cor`. Après validation, sélectionner les étapes pour inspecter leurs CoR et exporter séparément `mission.json` et `blueprint.json`. La compilation et la validation sont de **vrais appels JSON-RPC** aux trois outils publics existants.

Aucune exécution LLM, aucune publication, aucune donnée conservée côté serveur, aucun cookie, aucun compte, aucun token. Les fichiers sont générés dans le navigateur seulement. Ne pas y saisir de secrets ni de données clients privées : le serveur est public et anonyme. Le formulaire ne déclenche jamais `execute_workflow` ni `recall_lessons`. Un contrat planifié n'est pas un livrable exécuté. Les agents de la liste représentent des rôles de workflow, pas des processus IA exécutants.

**Lancer les tests :** `python3 -m unittest discover -s skills/numtema-synapse/tests -q`. Interface responsive : `GET /mcp`. API publique : `POST /mcp`, SSE historique : `GET /sse` puis `POST /messages`.

## Évolution v0.4.1 — passerelle MCP publique sans authentification

La passerelle HTTP expose `POST /mcp` **sans login, token, Bearer ni OAuth**. Les seuls outils publics sont `numtema.list_agents`, `numtema.validate_cor`, `numtema.compile_blueprint` et `numtema.plan_workflow`. Les fonctions `execute_workflow` et `recall_lessons` sont interdites à distance, même si un client fournit un en-tête Authorization ou prétend être administrateur.

Le code est testé localement. **Le serveur Coolify existant n'a pas été modifié.** Déployer d'abord sur un service de staging distinct ; l'endpoint `/sse` existant n'est pas remplacé. Toute personne sur Internet pourra utiliser le service public : ne jamais y connecter des données privées, secrets ou outils d'action. HTTPS, limites de débit et de connexions côté proxy restent nécessaires. Voir `skills/numtema-synapse/references/mcp-hosted-v04.md`.

## Ce qui est réellement exécutable

- `scripts/agent_forge.py` : compilation d'un blueprint en contrats CoR 2.0 et DAG.
- `scripts/forge_runtime.py` : moteur local de DAG, contrôles déterministes, corrections bornées, reprise SQLite optionnelle et approbations host-only pour adaptateurs sensibles.
- `scripts/mcp_server.py` : serveur stdio MCP **réel**, sans dépendance Python externe, avec six outils : liste d'agents, validation CoR, compilation, planification, exécution locale opt-in et lecture opt-in des leçons.
- Compatibilité JSON-RPC testée pour le protocole MCP `2026-07-28` (nouveau `server/discover`) et les initialisations héritées `2025-11-25`, `2025-06-18`, `2025-03-26`.

## Démarrage rapide (Python 3.11+)

Depuis le dossier de ce ZIP après extraction :

```bash
python3 -m unittest discover -s skills/numtema-synapse/tests -v
python3 skills/numtema-synapse/scripts/mcp_server.py < skills/numtema-synapse/examples/mcp-protocol-demo.jsonl
```

Les commandes ci-dessus vérifient la suite et affichent trois réponses MCP sans exécuter de mission.

Pour qu'un **hôte MCP stdio local** le lance, utiliser la configuration proposée dans `skills/numtema-synapse/examples/mcp-host-config.example.json` après adaptation du chemin absolu. Par défaut, la commande de lancement est :

```bash
python3 skills/numtema-synapse/scripts/mcp_server.py
```

Autoriser les **adaptateurs locaux uniquement** :

```bash
python3 skills/numtema-synapse/scripts/mcp_server.py --allow-execute
```

Exécution reproductible hors MCP :

```bash
python3 skills/numtema-synapse/scripts/agent_forge.py skills/numtema-synapse/examples/blueprint-landing-page.json --output /tmp/numtema-mission.json
python3 skills/numtema-synapse/scripts/forge_runtime.py /tmp/numtema-mission.json --execute
```

## Sécurité et confidentialité

L'exécution MCP est désactivée sans `--allow-execute`. Même activée, seuls quatre adaptateurs locaux de lecture/rédaction existent : `local.echo`, `local.extract_fields`, `local.render_template` et `local.assert_contains`. Aucun shell, HTTP, publication, publicité ou paiement n'est disponible ; les autorisations sensibles ne peuvent pas être forgées par les paramètres de mission. Aucune clé et aucun compte client ne figurent dans le ZIP. La mémoire persistante est **désactivée par défaut** : `--state-db` pour les reçus locaux, `--lessons-db` pour lire des leçons SQLite. Contrôler la rétention et les accès aux fichiers si ces options sont utilisées.

Les tests unitaires, d'intégration et transport **ne constituent pas une certification MCP officielle ni une validation par un client MCP externe**.

## Utilisation dans ChatGPT

Le plugin privé fournit son skill et les fichiers sources. **L'ajout du plugin ne lance pas son serveur Python local, ne connecte aucun compte et ne crée pas un endpoint MCP hébergé.** Le serveur fonctionne uniquement lorsqu'un hôte compatible le démarre explicitement. Le mode conversationnel du skill reste utilisable dans ChatGPT sans le runtime.

Documentation : `skills/numtema-synapse/references/mcp-stdio-v03.md` (local) et `skills/numtema-synapse/references/mcp-hosted-v04.md` (HTTP public sans auth).
