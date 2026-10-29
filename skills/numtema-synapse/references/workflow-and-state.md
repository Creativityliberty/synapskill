# Workflow, buffers, mémoire, morphismes et Vortex

## Chaîne canonique de mission

`IntentEnvelope → DecodedIntent → MissionSpec → ContextPack → ExecutionGraph → Artifacts → Verification → MissionReceipt`

- **IntentEnvelope** : texte brut, contexte déjà disponible, attentes et ambiguïtés.
- **DecodedIntent** : but réel, demande explicite vs inférences, enjeux et format.
- **MissionSpec** : critères de réussite et contrats parent/enfants.
- **ContextPack** : sources vérifiées, capacités réellement disponibles, permissions, limites.
- **ExecutionGraph** : étapes, dépendances, possibilités de parallèle, contrôles.
- **Artifacts** : fichiers, réponses, résultats avec références et version.
- **Verification** : tests automatiques, revue factuelle, verdicts.
- **MissionReceipt** : statut, livrable, preuves, limites, suite.

## Buffers (concepts de travail)

- `Goal Buffer` : objectifs actifs, indicateurs d'avancement, bloqueurs.
- `Retrieval Buffer` : références, provenance, fraîcheur et niveau de confiance.
- `Procedural Buffer` : règles, outils et approbations.
- `Visual Buffer` : designs, schémas et rendus.
- `Artifact Buffer` : sorties, versions et handoffs.
- `U_reasoning_state` : état opérationnel, pas pensées privées.
- `U_KG` : graphe de faits/symboles vérifiés si stockage disponible.
- `U_mem` / MorphologicalMemory : enseignements *validés* et pertinents, avec provenance et politique de conservation.

## U₀ et morphismes

- `U₀` désigne le noyau conceptuel commun qui maintient objectifs, contraintes et invariants entre transformations.
- Un **morphisme** est une transformation explicite : `f: Entrée typée → Sortie typée` avec préconditions, contraintes et tests de conservation.
- `U_morphism_registry` répertorie ces transformations ; chacune doit préciser entrée, sortie, postconditions, outils et critères de réversibilité.
- `agents-as-morphisms` est une *abstraction*, non une preuve de multi-agents exécutés.
- Les graphes DAG/Morsels subdivisent la mission en unités à sorties identifiables avec reprises partielles ; au stade skill, cela reste une convention. Pour l'exécuter automatiquement, il faut un moteur doté de stockage et d'ordonnancement.

## Etats et événements

`DRAFT`, `READY`, `RUNNING`, `REVIEW`, `REVISION`, `COMPLETED`, `BLOCKED`, `FAILED`.

Un journal d'événements, quand disponible, conserve : identifiant de contrat, événement, date, action réelle, résultat, erreurs, origine et artefacts. Ne pas inventer d'horodatages ou de traces.

## Reprise et stabilité

- Ne pas réexécuter les tâches dont les résultats demeurent valides.
- Sur échec d'une dépendance : bloquer les dépendants, limiter la reprise au sous-graphe concerné.
- Les changements externes sensibles nécessitent approbation, indépendamment du nombre de révisions.
- `/save` est une synthèse portable, non une écriture persistante garantie.
