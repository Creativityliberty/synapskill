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
