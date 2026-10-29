# Nümtema Synapse MCP — serveur stdio local v0.3

## Statut de l'implémentation

Implémentation **locale**, testée au niveau JSON-RPC et transport stdio, en Python standard (>=3.11) sans dépendances Python tierces. Protocole pris en charge : `2026-07-28` (`server/discover`, métadonnées par requête, résultat `resultType:complete`), et handshake `initialize` pour `2025-11-25`, `2025-06-18` et `2025-03-26`. **Ce n'est pas une certification officielle d'interopérabilité MCP.** Les outils sont les capacités réelles : aucune exécution de modèles IA autonomes, aucune connexion ChatGPT automatique, aucun accès HTTP, fichier arbitraire, shell, dépenses, déploiement ou compte publicitaire.

## Démarrage depuis la racine du paquet

```bash
python skills/numtema-synapse/scripts/mcp_server.py
# Par défaut: lecture, compilation, validation et planification uniquement.
# Le serveur reste en écoute stdin/stdout tant que le client le maintient.
```

**Exécution locale explicitement autorisée uniquement** :

```bash
python skills/numtema-synapse/scripts/mcp_server.py --allow-execute
```

L'option permet uniquement les quatre outils internes `local.echo`, `local.extract_fields`, `local.render_template`, `local.assert_contains` ; elle n'ajoute aucune capacité externe. Le `ForgeRuntime` ne prend aucune autorisation `grants` depuis le JSON transmis par le client MCP. Les opérations `external_write`, `financial_spend`, `deployment` restent indisponibles.

Pour un hôte MCP qui accepte des serveurs stdio locaux, configurer une commande avec le chemin absolu *vers votre copie installée* de `mcp_server.py`. Exemple dans `examples/mcp-host-config.example.json`. Ne pas copier aveuglément ce fichier dans les dossiers système : adapter les chemins et les réglages de l'hôte. Ne pas prétendre que le simple plugin ChatGPT lance le processus.

## Outils exposés

| Nom MCP | Entrée | Résultat | Risque / statut |
|---|---|---|---|
| `numtema.list_agents` | `{}` | profils de rôles | lecture, aucune sous-instance IA |
| `numtema.validate_cor` | `{contract}` | rapport de structure | aucun effet de bord |
| `numtema.compile_blueprint` | `{blueprint}` | `MissionSpec` + contrats CoR | pas d'exécution |
| `numtema.plan_workflow` | `{mission}` | plan DAG / blocage | pas d'exécution |
| `numtema.execute_workflow` | `{mission}` | reçu d'exécution | bloqué sauf `--allow-execute`; adaptateurs locaux uniquement |
| `numtema.recall_lessons` | `{scope, limit?}` | leçons exactes scope | retour `NOT_CONFIGURED` sauf `--lessons-db` |

Ordre de mission recommandé : `compile_blueprint` → `plan_workflow` → `execute_workflow` (si autorisé) → vérifier les `CoR_Result`.

## Permissions, mémoire, reprise

- Aucun tool MCP n'accepte de `grants`, `token`, `credential`, ou un registre de fonctions injecté côté client.
- Adapter-only : pas d'enregistrement dynamique d'outils par le client. Le registre des profils d'agents ne crée pas de workers LLM.
- `--state-db ./state/receipts.sqlite` : opt-in à la persistance des événements et sorties des tâches locales ; **peut contenir du texte de mission**, à protéger et purger selon les besoins.
- `--lessons-db ./state/lessons.sqlite` : lecture opt-in de leçons locales ; **aucun tool MCP d'écriture mémoire** n'est exposé. Les écritures par API Python exigent `approved=True` de l'hôte de confiance.
- Les résultats de tâches non sensibles peuvent être repris par empreinte (cache SQLite). Les opérations sensibles, si un hôte tiers devait en enregistrer plus tard, restent sans retry automatique.
- Le protocole limite la taille d'un message à 1 Mo et le nombre d'appels à 100/min par défaut, configurable au lancement de 1 à 1000/min. Le transport est `stdio` ; aucune interface HTTP publique.
- Les contrôles `mandatory_checks` et `required_text` sont mécaniques, **pas des preuves de validité marketing ou factuelle**.

## Exemples de messages MCP 2026-07-28

Découverte :

```json
{"jsonrpc":"2.0","id":1,"method":"server/discover","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientInfo":{"name":"local-test","version":"1"},"io.modelcontextprotocol/clientCapabilities":{}}}}
```

Pour exécuter un test en ligne de commande sur le fichier JSONL déjà fourni :

```bash
python skills/numtema-synapse/scripts/mcp_server.py < skills/numtema-synapse/examples/mcp-protocol-demo.jsonl
```

La sortie fournit trois réponses JSON-RPC (découverte, liste d'outils, profils).

## Tests

```bash
python -m unittest discover -s skills/numtema-synapse/tests -v
```

Tests spécifiques : requêtes modernes et legacy, framing JSONL stdin/stdout, validation des outils, blocages par défaut, limites de débit, scénarios d'autorisations forgées, absence de shell/web/spend, DAG, Reflexion et suite des versions précédentes.

## Limites assumées

- Un hôte compatible est nécessaire pour lancer un serveur stdio. ChatGPT n'exécute pas automatiquement des scripts Python embarqués dans les skills.
- Aucun service hébergé HTTP/Streamable HTTP, OAuth, serveur distant ni connecteur lié aux comptes clients dans cette version.
- Le serveur expose un petit sous-ensemble MCP (découverte, outils, ping, initialisation legacy). Les autres fonctionnalités MCP (resources, prompts, streaming, subscriptions, tasks) sont non implémentées.
- L'implémentation protocolaire est autonome ; pour une production à grande échelle, préférer un SDK MCP officiel, un environnement isolé, supervision, contrôles de charge, permissions par utilisateur et tests d'interopérabilité par un hôte réel.

## Références MCP

- https://modelcontextprotocol.io/specification/2026-07-28/server/discover
- https://modelcontextprotocol.io/specification/2026-07-28/server/tools
- https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning
