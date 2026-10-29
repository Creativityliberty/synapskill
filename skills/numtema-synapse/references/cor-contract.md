# Synapse_CoR 2.0 — contrat de mission

Un agent reçoit un **contrat borné**, pas seulement une personnalité. Douze sections obligatoires :

1. `identity` : id, responsable, compétence, superviseur.
2. `mission` : objectif unique, résultat observable, importance.
3. `context` : faits, audience, risques, provenance, hypothèses explicites.
4. `inputs` : données requises/facultatives, politique de manque.
5. `scope` : inclus, exclus, dépendances.
6. `tools` : allowlist des outils réellement accessibles et route de repli.
7. `permissions` : lecture, brouillon, écriture, publication, dépenses, validation humaine.
8. `deliverables` : forme, schéma, critères de complétude.
9. `validation` : tests obligatoires, preuve externe, revue indépendante si pertinent.
10. `handoff` : receveur, résultats, preuve, limites, décisions ouvertes.
11. `reflection` : feedback, nombre maximum de révisions et critère de progrès.
12. `termination` : réussite, blocage, échec, attente d'approbation.

## Contrat parent / enfants

`permissions(child) ⊆ permissions(parent) ∩ permissions(runtime)`.

Ne pas traiter cette écriture comme un mécanisme de sandbox : seuls les contrôles du runtime et de chaque outil sont exécutoires. En absence d'outil de permission, toutes les actions externes doivent respecter les autorisations et confirmations applicables.

## Autonomie graduée (profil conceptuel)

- A0 : analyse uniquement ; A1 : projet local/brouillon ; A2 : lecture assistée d'outils disponibles ; A3 : écriture extérieure uniquement après autorisation explicite ; A4 : opération à fort impact avec contrôle humain renforcé et garde-fous du runtime.
- En mode prompt, ces niveaux sont des conventions de procédure, pas des barrières techniques.
- Ne pas permettre des dépenses, suppressions, déploiements ni publications sur simple auto-approbation du CoR.

## Handoff standard : `CoR_Result`

```json
{
  "contract_id": "COR-001",
  "status": "COMPLETED",
  "deliverables": {"artifact": "exemple"},
  "validation": {"mandatory_passed": true},
  "evidence": [],
  "assumptions": [],
  "unresolved_issues": [],
  "next_action": "HANDOFF_TO_ORCHESTRATOR"
}
```

Ne jamais rendre `COMPLETED` si un check obligatoire échoue ; choisir `BLOCKED` ou `FAILED` si nécessaire.
