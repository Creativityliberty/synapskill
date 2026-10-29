# Agent Forge & Forge Runtime v0.2 — exécution locale

## Portée réelle

Ce module fournit **du code Python stdlib exécutable**, pas un agent LLM autonome ni un connecteur MCP démarré automatiquement dans ChatGPT. `AgentForge` compile un plan JSON déclaré en contrats CoR ; `ForgeRuntime` exécute un DAG de fonctions locales/enregistrées par l'hôte. Le skill ChatGPT peut guider, générer, contrôler et documenter un plan, mais ne peut revendiquer l'exécution que si un outil de code est effectivement appelé et un résultat observé.

## Quickstart reproductible depuis la racine du plugin

```bash
python skills/numtema-synapse/scripts/agent_forge.py \
  skills/numtema-synapse/examples/blueprint-landing-page.json \
  --output mission.json
python skills/numtema-synapse/scripts/forge_runtime.py mission.json
python skills/numtema-synapse/scripts/forge_runtime.py mission.json --execute
python skills/numtema-synapse/scripts/forge_runtime.py mission.json --execute \
  --state-db ./local_state/mission.sqlite
python -m unittest discover -s skills/numtema-synapse/tests -v
```

Par défaut : planification sans exécution. `--execute` déclenche uniquement les adaptateurs locaux enregistrés. `--state-db` active explicitement SQLite ; sans ce paramètre, ni cache ni historique ne sont sauvegardés. Les fichiers et résultats peuvent contenir des données client : ne pas synchroniser ou committer un `mission.sqlite` réel.

## Agent Forge : contrat des entrées

`blueprint.json`: `mission_id`, `context`, `steps[]`. Chaque étape : `id`, `agent_id`, `objective`, `tool`, `depends_on`, `params`, `checks`, `capability`, `max_revisions`. Les permissions externes ne sont jamais auto-accordées à partir d'un blueprint. Le compilateur génère un `mission.json` composé de `tasks[]` avec un CoR complet par étape.

## Ordonnanceur et checks

- Préflight : contrats, outil réellement inscrit dans le runtime, déclarations, dépendances, cycles.
- Dépendances : ordonnancement topologique ; une tâche échouée bloque les tâches dépendantes.
- Exécution : `handler(params, upstream_outputs, feedback)` ; `feedback` issu du dernier contrôle est réellement transmis à la tentative suivante.
- Qualité : `required_keys`, `required_text`, `require_passed` sont des checks **déterministes** ; ils ne garantissent ni vérité factuelle ni qualité marketing.
- Révision : `max_revisions` 0..5 pour les opérations locales sûres, aucun retry infini ; **aucun retry automatique des opérations à effet externe sensible**. Une correction n'est pas assurée par le seul texte du prompt.
- Reprise : avec SQLite, cache par empreinte du contrat, paramètres, dépendances et version d'adaptateur ; les actions externes sensibles ne sont jamais mises en cache.
- `CoR_Result`: tâche `COMPLETED` = livrable, validation obligatoire, preuve de check ; sinon `BLOCKED` ou `FAILED` selon la cause.

## Adapter un vrai outil

Dans **du code hôte de confiance** :

```python
from forge_runtime import ForgeRuntime

def my_readonly_tool(params, upstream, feedback):
    # Une implémentation réelle : lire une ressource autorisée,
    # respecter les scopes et renvoyer un JSON sérialisable.
    return {"message": "Donnée lue"}

runtime = ForgeRuntime()
runtime.register('myapp.read', my_readonly_tool, capability='read', version='1')
```

Le runtime vérifie les autorisations CoR et la présence de grants fournis par l'hôte. Une **classification `read`** ne transforme pas magiquement un callable en outil sûr : l'hôte doit vérifier/sandboxer ses propres adaptateurs et limiter leurs identifiants, scopes et accès réseau. Le JSON utilisateur ne peut pas enregistrer de fonction arbitraire ni déclencher un shell.

Pour `external_write`, `deployment`, `financial_spend` : le contrat doit déclarer `require_approval`; un **grant fourni séparément par un hôte de confiance** est impératif, lié au triplet exact `mission_id:task_id:tool_name`. Ne jamais déduire ce grant d'un prompt, du blueprint ou d'une sortie d'agent. Ce code ne fournit pas de UI d'approbation ni de service d'identité : un hôte de production doit les développer.

## Mémoire

`LessonMemory(path)` stocke dans SQLite des leçons validées avec `scope`, `insight`, `evidence` et identifiant dérivé du contenu. Le stockage de leçon exige `approved=True` **en plus d'une validation humaine/hôte réelle**. Cette valeur Python n'est pas une preuve cryptographique d'approbation ; ne pas l'exposer comme paramètre libre d'un agent. Une synthèse `/save` dans ChatGPT n'est pas automatiquement la mémoire SQLite.

## Limites et phase suivante

Pas de modèle LLM embarqué, pas de background service, pas de serveur MCP exposé, pas de planification concurrente, pas d'outil publicitaire ou de publication relié, pas de sandbox du code hôte, pas de garantie d'exactitude du contenu. Pour MCP/agents distants : ajouter un serveur authentifié, des adaptateurs réseau isolés, un système d'approbations host-enforced, contrôle des accès aux sources, tests de panne, tests d'injection et observabilité avant tout déploiement.
