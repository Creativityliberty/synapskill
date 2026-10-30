# Cognitive Memory v0.8 — Mémoire privée, approuvée et effaçable

## Objectif

Faire remonter **uniquement des enseignements examinés par un opérateur** après un workflow CoR réellement marqué `COMPLETED`, dont le dernier contrôle Reflexion est `PASSED` et correspond au SHA-256 exact du livrable. Cela ne certifie ni la vérité factuelle ni l'origine des preuves : un verdict LLM reste heuristique et l'approbation humaine est une décision explicite distincte.

Cette mémoire n'est **pas** la fonction `LessonMemory` historique du runtime v0.2 et ne remplace pas la mémoire de compte ChatGPT. Elle vit dans une base SQLite propriétaire du processus privé. Le worker se contente de la lire et **n'écrit jamais une leçon automatiquement**, même après un succès Reflexion.

## Flux de confiance

```text
Mission Studio public (4 outils, aucun accès mémoire)
       -> export mission.json/blueprint.json
       -> opérateur privé : Ollama --execute --reflexion --output ./report.json
       -> examen humain du rapport et du texte produit
       -> CLI opérateur memory_cli.py approve (écriture explicitement autorisée)
       -> SQLite privée approuvée (durée finie, portée exacte, preuve SHA-256)
       -> worker privé : --memory-db + --memory-scope (lecture seule)
       -> leçons transmises comme données NON fiables dans le prompt
```

## Conditions d'admission

1. Rapport de mission `COMPLETED` avec identifiant ; tâche `COMPLETED` ; `validation.mandatory_passed=true`.
2. Dernier rapport Reflexion de la tâche : `status=PASSED`, liste `issues=[]` et `candidate_sha256` égal au SHA-256 calculé sur le livrable exact.
3. L'opérateur examine réellement le texte et rédige **manuellement** une leçon courte (pas de copie automatique des sorties du modèle), puis ajoute le drapeau explicite `--operator-reviewed` depuis un terminal de confiance.
4. La leçon est portée par un identifiant de projet (`--scope`) choisi côté opérateur, pas déduit du contenu fourni par un visiteur public.

## Exemple de cycle, depuis la racine du dépôt

```bash
# 1. Créer un rapport en environnement privé (Ollama installé ; exemple fictif)
python3 skills/numtema-synapse/scripts/llm_runtime.py \
  skills/numtema-synapse/examples/blueprint-local-llm.json \
  --model gemma3:1b --reflexion --execute --output ./rapport-prive.json

# 2. L'opérateur relit le rapport ET le livrable ; puis approuve une leçon spécifique.
python3 skills/numtema-synapse/scripts/memory_cli.py \
  --db ./state/cognitive-private.sqlite approve \
  --report ./rapport-prive.json --task-id draft --scope projet-demo \
  --insight 'Conserver un CTA explicite et ne jamais inventer de témoignages' \
  --retention-days 30 --operator-reviewed

# 3. Employer la mémoire EN LECTURE SEULE lors d'une future mission privée.
python3 skills/numtema-synapse/scripts/llm_runtime.py \
  skills/numtema-synapse/examples/blueprint-local-llm.json \
  --model gemma3:1b --reflexion --execute \
  --memory-db ./state/cognitive-private.sqlite \
  --memory-scope projet-demo --memory-limit 5

# 4. Examiner / effacer (depuis un terminal privé)
python3 skills/numtema-synapse/scripts/memory_cli.py \
  --db ./state/cognitive-private.sqlite recall --scope projet-demo
python3 skills/numtema-synapse/scripts/memory_cli.py \
  --db ./state/cognitive-private.sqlite purge-expired --confirm
python3 skills/numtema-synapse/scripts/memory_cli.py \
  --db ./state/cognitive-private.sqlite purge-scope --scope projet-demo --confirm
```

Si `draft` n'est pas l'identifiant de tâche du rapport, remplacer `--task-id` par l'identifiant exact. La commande d'approbation doit être lancée seulement après contrôle humain, même si le statut `PASSED` apparaît.

## Données stockées

- `id` : SHA-256 de la leçon + périmètre + référence de preuve.
- `scope` : clé de projet exacte, sans partage implicite entre périmètres.
- `insight` : seule formulation courte fournie et relue par l'opérateur (600 caractères maximum).
- `evidence` : identifiants mission/tâche, empreinte SHA-256 du candidat et nom du modèle critique, si fourni.
- `approved_at`, `expires_at`, `provenance` : date UTC, expiration, type de validation humaine.

**Ne sont pas stockés :** le contenu complet des sorties, les messages de modèle, les prompts, les dossiers clients, les secrets ou l'historique de conversation. Une leçon contient néanmoins un texte lisible : ne pas y placer de données sensibles. Le chiffrement au repos n'est pas fourni ; le fichier SQLite est créé en permission POSIX `0600`, et les données sur disque doivent rester sur un volume privé chiffré et sauvegardé suivant la politique de l'opérateur.

## Retention et suppression

- Durée explicite 1 à 365 jours, 30 jours par défaut. Les entrées expirées ne sont plus rappelées.
- La suppression physique des lignes expirées requiert `purge-expired --confirm` ; ce n'est **pas** un cron automatique.
- `delete --id SHA256 --scope ... --confirm` supprime une entrée ; `purge-scope --scope ... --confirm` supprime toutes les entrées d'un projet. Après suppression, backups/snapshots peuvent encore contenir les anciennes données : gérer leur cycle séparément.
- La duplication de la même leçon n'étend pas l'expiration.
- Les limites de la base et du cache du système de fichiers ne constituent pas une garantie de destruction forensic.

## Défense et limites

- `memory_cli.py` n'est ni outil MCP ni endpoint web. L'API HTTP/SSE publique reste strictement limitée à `list_agents`, `validate_cor`, `compile_blueprint`, `plan_workflow` et n'a aucun accès à la DB.
- L'option worker `--memory-db` ouvre la DB **en lecture seule** (`SQLite mode=ro`) et échoue si absente ou non configurée. `--memory-scope` est obligatoire avec `--memory-db` ; aucun apprentissage implicite.
- La mémoire récupérée est réinjectée dans un champ `approved_lessons_untrusted_data` : ses textes ne constituent pas des instructions système. Les injections peuvent néanmoins influencer un modèle : ne mémoriser que des formulations sûres, relues par un humain.
- L'isolation par scope est **logique et non une isolation multitenant cryptographique**. Elle repose sur un opérateur/worker privé de confiance. Pas de compte public, pas de tenant ajouté, pas de permissions nouvelles accordées aux utilisateurs anonymes.
- Aucune promesse de modèle réel Ollama exécuté tant qu'un hôte Ollama n'a pas été vérifié.

## Vérification

`python3 -m unittest discover -s skills/numtema-synapse/tests -q`

Les tests vérifient l'approbation obligatoire, les limites du contrat, les empreintes, le TTL, les purges, le confinement des scopes, l'accès SQLite en lecture seule pour le worker, les commandes CLI et l'absence d'outil mémoire sur la passerelle anonyme.
