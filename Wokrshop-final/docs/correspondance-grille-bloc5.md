# Correspondance grille Bloc 5 ↔ livrables

**BLOC 5** — Concevoir et mettre en œuvre l'architecture d'un SI (spécialité Systèmes et Réseaux)  
**Projet** — M2-Shop, observabilité sécurisée

Un seul PoC, plusieurs livrables. À l'oral : *« Le PoC valide le cahier des charges : chaque flux a un test, le déploiement est IaC, la recette du 7 septembre le reproduit. »*

| Compétence | Livrable attendu | Fichier | Quoi montrer |
| --- | --- | --- | --- |
| **C5.1.1** Cartographier l'existant | Cartographie SI | `docs/C5.1.1-C5.1.2-cartographie-et-contraintes.md` § 1 | Avant (LAN plat) → cible 3 zones |
| **C5.1.2** Orientations et contraintes | Analyse | Même fichier, § 2 | ANSSI, métier, Windows/`ansible_local`, pas de backup |
| **C5.1.3** Cahier des charges | Synthèse technique | DAE § 1 + `docs/matrice-de-flux.md` | 4 flux FORWARD, 2 plans, jalons A–D |
| **C5.2.1** Concevoir l'architecture | Présentation | DAE § 1.1–1.4 + `docs/hld-lld-architecture.md` | HLD / LLD + schéma `architecture-m2shop.png` |
| **C5.2.2** Cahier de recettes | Scénario de test | `docs/tests-de-validation.md` | Commande / attendu / obtenu |
| **C5.2.3** PoC | Démonstration | `docs/demo-jury.md` + VMs + Grafana | Timeout 22, dashboard, healer 21:13:44 |
| **C5.3.1** Déployer / intégrer | Protocole d'intégration | `docs/C5.3.1-C5.3.2-protocole-integration.md` | `ansible_local`, `--limit`, justification |
| **C5.3.2** Automatiser | Méthode | Même fichier + rôles Ansible + `healer` | Provisioning + remédiation bornée |
| **C5.3.3** Campagne de tests | Compte-rendu | `docs/tests-de-validation.md` (fin) | Campagne du 7 septembre 2026 |
| **C5.4.1** Documentation | Guide utilisateur / admin | `docs/C5.4.1-guide-utilisation-sre.md` | Grafana, interdits, PCO, reconstruction |

## Dossier de soutenance (4 pièces)

1. **DAE** (`Rendu-Final-DAE-Complet-M2Shop-Observabilite-Securisee.md`) — C5.1.3, C5.2.1, PCO, § 3.2 sauvegardes  
2. **Recette + CR** (`docs/tests-de-validation.md`) — C5.2.2, C5.3.3  
3. **PoC** (`docs/demo-jury.md`, captures Grafana, `remediation.log`) — C5.2.3  
4. **IaC** (`Vagrantfile`, `ansible/site.yml`, `docs/C5.3.1-C5.3.2-protocole-integration.md`) — C5.3.1, C5.3.2  

C5.1.1 / C5.1.2 et C5.4.1 sont les annexes dédiées (créées pour les lignes non couvertes par le DAE seul).
