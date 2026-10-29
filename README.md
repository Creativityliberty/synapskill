# Nümtema Synapse Cognitive OS — v0.3.0

**Skill + plugin privé + serveur MCP stdio local** pour orchestrer des missions CoR gouvernées par RRLA, Synapse, Reflexion, Morphius et Agent Forge. Propriété Nümtema (voir `LICENSE.md`).

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

Documentation détaillée : `skills/numtema-synapse/references/mcp-stdio-v03.md`.
