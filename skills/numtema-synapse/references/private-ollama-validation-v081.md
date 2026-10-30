# Nümtema Synapse v0.8.1 — Validation privée Ollama (Coolify/Docker)

## Objectif / frontières

Valider une **vraie** inférence Ollama, un livrable CoR et une revue Reflexion sur une infrastructure Docker privée. La seule UI publique reste Synapse Mission Studio (`GET /mcp`) avec les **quatre outils MCP de préparation** déjà autorisés. Aucun port Ollama/worker ne doit être exposé, aucune authentification utilisateur n'est ajoutée et aucun contenu client réel n'est utilisé pendant le test.

Il s'agit d'une installation séparée, pas d'une modification de l'application publique. Le code et les tests locaux ne démontrent pas qu'Ollama tourne déjà sur Coolify. La validation n'est réussie qu'en présence d'un rapport `status=GO` généré **sur le serveur privé**.

## Pré-requis

- Serveur Linux sous Docker Engine + Compose v2 (par exemple sur un hôte Coolify, via terminal de confiance). Accès CLI d'opérateur au dépôt GitHub.
- RAM libre recommandée 4 Go minimum, disque disponible pour image Ollama + modèle + couches Python. Ressources effectives à adapter à l'hôte ; CPU peut être lent. Aucun GPU obligatoire pour `gemma3:1b`.
- Accès à Internet **uniquement pendant le téléchargement initial** du modèle, pas pendant son exécution interne.
- Aucun domaine ni proxy Coolify configuré sur la nouvelle pile privée.

Le modèle de démonstration est `gemma3:1b` (texte, environ 806 Mo à télécharger selon le registre Ollama, chiffre susceptible de varier). Consulter la documentation officielle : https://ollama.com/library/gemma3 et https://docs.ollama.com/api.

## Étape 1 — Installer le modèle, sans port publié

Depuis la racine du dépôt :

```bash
docker compose -f deployment/ollama-bootstrap.compose.yml config
docker compose -f deployment/ollama-bootstrap.compose.yml up -d ollama
docker compose -f deployment/ollama-bootstrap.compose.yml exec -T ollama ollama pull gemma3:1b
docker compose -f deployment/ollama-bootstrap.compose.yml exec -T ollama ollama list
docker compose -f deployment/ollama-bootstrap.compose.yml down
```

**Ne pas ajouter `-v` à `down`** : le volume persistant `synapse_private_ollama_models` doit conserver le modèle. La pile bootstrap est volontairement connectée à un réseau sortant, mais ne publie jamais `11434`. Arrêter bootstrap avant de démarrer le réseau totalement interne pour l'inférence.

## Étape 2 — Démarrer Ollama isolé

```bash
docker compose -f deployment/ollama-private.compose.yml config
docker compose -f deployment/ollama-private.compose.yml up -d ollama
docker compose -f deployment/ollama-private.compose.yml ps
```

La pile privée porte un réseau Docker `internal: true` ; ni Ollama ni le worker ne déclarent `ports`/`expose`/labels de reverse proxy. Le worker est un profil `manual`, donc il ne démarre pas pendant `up -d` : il faut explicitement l'invoquer.

### Contrôle d'absence d'exposition

Sur l'hôte :

```bash
docker compose -f deployment/ollama-private.compose.yml ps
docker ps --format 'table {{.Names}}\t{{.Ports}}'
```

Vérifier que **le service Ollama de cette pile ne possède aucun port publié sur l'hôte** ; vérifier dans Coolify qu'aucun domaine n'a été attribué au conteneur. Les configurations Docker/Coolify réelles peuvent ajouter des réseaux ou des proxys : inspecter ce qui est effectivement en cours d'exécution et ne pas déduire la sécurité du YAML seul.

## Étape 3 — Vérifier une véritable mission

```bash
# Aucune exécution distante, aucune mémoire SQLite, aucune donnée client.
docker compose -f deployment/ollama-private.compose.yml run --rm -T worker > /tmp/synapse-private-e2e.json
cat /tmp/synapse-private-e2e.json
```

L'image worker démarre `private_live_probe.py` avec `--execute` explicite et :

1. demande `GET /api/tags` sur `http://ollama:11434` et vérifie `gemma3:1b` ;
2. appelle `POST /api/chat` avec `format: json` et vérifie une petite réponse structurée ;
3. exécute le blueprint **fictif** et son DAG, impose les contrôles CoR et un second appel de revue Reflexion ;
4. imprime un reçu minimal **sans texte intégral produit par le modèle**. Il ne stocke aucune leçon.

Le verdict `GO` requiert un workflow COMPLETED et au moins une revue PASSED, avec des appels modèle comptabilisés. Un modèle qui ne respecte pas le contrat donnera légitimement NO_GO. En cas de refus du modèle, examiner ses sorties **dans un environnement privé** et ajuster le modèle/le brief ; ne jamais retirer les garde-fous publics pour obtenir artificiellement GO.

Le rapport contient `elapsed_seconds`, `model_calls`, `checks`, `workflow`, `status` et `reason`, sans identifiants ou secrets. Le `GO` prouve que le circuit de test a fonctionné sur l'hôte courant ; il **ne certifie ni la qualité factuelle du texte, ni une isolation multiclient, ni la sécurité globale de l'infrastructure**.

## GO / NO-GO

| Contrôle | GO | NO-GO |
|---|---|---|
| Modèle | `GET /api/tags` répond, modèle installé | indisponible ou manquant |
| JSON | `POST /api/chat` livre un objet attendu | JSON erroné, timeout, erreur |
| CoR | toutes les tâches terminées et vérifiées | blocage, validation échouée |
| Reflexion | revue PASSED et au moins deux appels du worker | aucune revue ou revue rejetée |
| Confidentialité | aucune route publique vers `11434`, aucune mémoire activée | port public / proxy / données privées |

Pour valider **l'instance Coolify** plutôt qu'un environnement isolé distinct, lancer ce protocole sur le même hôte privé et conserver son reçu. Une réponse GET de `/mcp` n'apporte aucune preuve du modèle privé. Ne jamais ajouter `execute_workflow` ou `recall_lessons` aux outils publics.

## Nettoyage

```bash
# Stopper les services de test sans effacer les modèles :
docker compose -f deployment/ollama-private.compose.yml down
# Supprimer volontairement le fichier de diagnostic local :
rm -f /tmp/synapse-private-e2e.json
# Ne pas ajouter -v à down sans intention de supprimer le modèle.
```

Aucun login, aucun jeton OAuth/Bearer. Les commandes Docker restent réservées à l'opérateur disposant déjà d'un accès sécurisé à son hôte ; cela ne revient pas à exposer l'accès Docker au public.
