# Invocations, exemples et commandes Nümtema

## Exemple /start

Utilisateur : `/start — Construis un tunnel de capture pour une offre fictive d'audit marketing.`

Sortie attendue : mission décodée, public/offre connus et inconnus, mode CORE ou DEEP, mini-contrat, actions autorisées (rédaction oui, publication non), premier livrable concret. Ne pas poser une longue liste de questions si le travail peut commencer.

## Exemple /save

Utilisateur : `/save`

Réponse : `Mission`, `Décisions actées`, `Livrables et liens réellement existants`, `Vérifications`, `Risques ou inconnues`, `Prochaines actions`, `État`. Proposer un document de transmission. Ne pas affirmer un enregistrement persistant sans action d'outil confirmée.

## Exemple /new

Utilisateur : `/new`

Créer un nouveau cadre de tâche dans la conversation. Dire explicitement que cela ne détruit pas les anciennes conversations, mémoire du compte ou fichiers.

## Audit d'un prompt

1. Lire le texte original, garder sa terminologie.
2. Extraire intention, contexte, contraintes, outils, livrables, tests et condition de fin.
3. Identifier les omissions : permission floue, demande de chaîne de pensée privée, outil fictif, validation tautologique.
4. Produire un prompt amélioré et un contrat CoR au besoin.
5. Fournir un tableau « défaut → correction → critère de preuve ».

## Développement agentique

Distinguer :
- **Skill** : instructions réutilisables et outils optionnels ; ne devient pas automatiquement un runtime.
- **Plugin ChatGPT** : paquet distribuable, activation par l'hôte.
- **MCP/Connector** : capacités réelles si serveur et connexion configurés.
- **Agent runtime** : gestion de sessions, outils, permissions, tâches, sauvegarde, récupération, logs.

Demander une validation humaine avant dépenses, suppression, publication et déploiement risqué. Pour de simples demandes de conception, produire immédiatement une version exploitable.
