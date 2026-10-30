# Synapse v0.6 — Agent Runtime IA privé (Ollama)

## Ce qui est implémenté

`skills/numtema-synapse/scripts/llm_runtime.py` exécute **réellement** les appels HTTP JSON vers `POST /api/chat` du serveur Ollama de l'opérateur lorsque `--execute` est présent. Le backend demande `format: json`, `stream: false` et limite les tokens générés. La réponse du modèle est interprétée en objet JSON, puis contrôlée par `ForgeRuntime` et les critères CoR. Aucun Ollama n'est automatiquement lancé/embarqué dans le plugin ChatGPT.

Le worker enregistre seulement `llm.draft` et `llm.review` **dans son processus local privé**, ainsi que les quatre adaptateurs déterministes du Forge Runtime. Aucun shell, navigateur, requête web décidée par le modèle, connexion externe, publication, email, paiement ou mise à jour de données n'est enregistré. Le résultat d'un LLM n'est jamais une permission.

## Exécuter depuis la racine du dépôt

```bash
# Un Ollama réellement installé et lancé sur cet ordinateur est nécessaire.
ollama list
python3 skills/numtema-synapse/scripts/llm_runtime.py \
  skills/numtema-synapse/examples/blueprint-local-llm.json \
  --model gemma3:1b
# Le résultat est PLANNED : aucun appel au modèle sans --execute.

python3 skills/numtema-synapse/scripts/llm_runtime.py \
  skills/numtema-synapse/examples/blueprint-local-llm.json \
  --model gemma3:1b --execute \
  --max-calls 8 --max-output-tokens 768 --timeout-seconds 45 \
  --output ./private-mission-result.json
```

Le modèle doit figurer dans `ollama list`; le nom `gemma3:1b` est un exemple de modèle à installer séparément. Les sorties sont locales, à l'emplacement explicitement donné. Les entrées peuvent être `blueprint.json` ou `mission.json` exportées par Mission Studio.

## Préparer depuis Mission Studio

Dans **Mission Studio** (`GET /mcp`), sélectionner **Préparer pour un agent IA local (Ollama)**, compiler, puis exporter le JSON. L'option transforme uniquement la tâche de rédaction en `llm.draft`, et conserve le contrôle `VerifierAgent` déterministe. Les appels publics `compile_blueprint`, `plan_workflow` et `validate_cor` restent des opérations de planification ; l'API ne peut pas invoquer `llm.draft` ou déclencher le worker. **Ne saisir aucune information privée dans l'interface publique.**

Un plan IA n'implique pas que le serveur hébergé dispose du modèle ni que la tâche puisse être lancée depuis le navigateur. Le worker privé doit être démarré par un opérateur dans un environnement privé.

## Déploiement Coolify

La solution la plus simple est une machine dédiée ou un **worker séparé**, jamais exposé par un domaine/port public. Ce worker peut utiliser une instance Ollama privée déjà existante sur le même hôte ou sur le réseau privé Docker de Coolify. Pour les conteneurs distincts, utiliser l'URL interne stable, par exemple `--url http://ollama:11434 --trusted-host ollama`, **uniquement si ce nom est connu et contrôlé par l'opérateur**. Ne pas publier le port Ollama 11434 ni un endpoint d'exécution du worker.

Le domaine public `synapse.coolify.dallico.com` continue d'utiliser la politique anonyme à quatre outils et n'expose pas le worker privé. Aucune authentification n'est nécessaire pour le *Studio de préparation*. Les permissions sont obtenues par la séparation de réseau et des processus : le navigateur n'a simplement pas d'accès au worker.

## Gouvernance et limites

- Par défaut, mode `PLANNED`, aucun appel modèle ; exécution **opt-in** `--execute` seulement.
- Le code refuse les URL de modèle avec identité, chemin, requête, redirection ou domaine non explicitement autorisé ; boucle locale autorisée par défaut.
- Le worker limite le payload, la longueur des prompts et réponses, le nombre d'appels (`--max-calls`), les tokens (`--max-output-tokens`) et le timeout de chaque appel.
- Les révisions Reflexion utilisent **le feedback effectivement réinjecté**, dans la limite contractuelle. Les tâches ayant des opérations sensibles ne sont jamais inscrites au registre de ce worker.
- La mémoire persistante du worker est **désactivée** ; aucun SQLite ni fichier de journal automatique.
- Un `COMPLETED` indique que les contrôles structuraux demandés ont réussi, pas que les allégations factuelles du modèle sont vérifiées, ni qu'un humain a accepté le livrable.
- Le protocole Ollama a été testé avec un **serveur local simulant ses réponses**. Un test avec un modèle réellement installé reste à faire sur la machine de l'opérateur.

## Vérification

```bash
python3 -m unittest discover -s skills/numtema-synapse/tests -q
python3 -m compileall -q skills/numtema-synapse/scripts
```

Les tests couvrent notamment la validation des hôtes, le JSON wire, les DAG, les budgets, l'injection de feedback, la non-exposition de l'IA aux outils MCP publics, et la planification IA depuis Mission Studio.
