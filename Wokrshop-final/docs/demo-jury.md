# Démo jury (5–7 min)

**C5.2.3** — démonstration du PoC (cohérence, efficacité, compatibilité avec le cahier des charges).

**Objectif** — montrer le PoC M2-Shop en conditions réelles, sans refaire un `vagrant up`.  
**Prérequis** — les 3 VMs déjà `running` ; Grafana ouvert en arrière-plan (`https://127.0.0.1:3443`).  
**Fil conducteur** — *« SI e-commerce cloisonné, observabilité chiffrée, recette rejouable, remédiation sans root partagé. »*

Ne pas improviser de `curl https://10.0.20.20/` depuis supervision (interdit en FORWARD). Toutes les commandes partent de l'hôte Windows.

| Minute | Étape | Compétences visées |
| --- | --- | --- |
| 0:00–1:00 | 1. Architecture | C5.1.3, C5.2.1 |
| 1:00–2:00 | 2. Zero-Trust | C5.2.1, C5.2.2 |
| 2:00–4:00 | 3. Observabilité | C5.2.3, C5.4.1 |
| 4:00–6:00 | 4. Auto-healing | C5.2.3, C5.3.2 |
| 6:00–7:00 | 5. IaC | C5.3.1 |

---

## Avant d'entrer (2 min, hors chrono)

```powershell
cd D:\lab-bloc5\TP-Mrdecker\Wokrshop-final
vagrant status
```

Attendu : `web-prod`, `fw-router`, `supervision` = `running`.

Ouvrir Chrome sur `https://127.0.0.1:3443` (certificat auto-signé : Accepter).  
Login labo : `admin` / `admin`. Laisser l'onglet **Dashboards → M2-Shop**.

Avoir un second onglet prêt : ce fichier, ou `ansible/site.yml`.

Si une VM est `poweroff` : `vagrant up` **avant** la soutenance, pas devant le jury.

---

## 1. Architecture (1 min)

**À dire** — Trois zones, aucun réseau commun prod/admin, tout passe par fw-router.

```powershell
vagrant status
vagrant ssh fw-router -c "ip -br a"
```

**À montrer** :

| Interface | IP | Rôle |
| --- | --- | --- |
| eth0 | 10.0.2.15 | NAT (SSH Vagrant depuis l'hôte) |
| eth1 | 10.0.20.1 | Patte DMZ Prod |
| eth2 | 10.0.10.1 | Patte DMZ Admin |

**Phrase de clôture** — *« fw-router n'est pas la gateway par défaut : des routes statiques forcent le next-hop. Sans elles, nftables FORWARD n'est jamais atteint. »*

---

## 2. Zero-Trust (1 min)

**À dire** — Un flux non listé timeout ; un flux autorisé traverse.

```powershell
vagrant ssh web-prod -c "timeout 5 nc -zv 10.0.10.5 22 || echo TIMEOUT_OK"
vagrant ssh supervision -c "curl -s http://localhost:9090/api/v1/targets"
```

**Attendu** :

- `TIMEOUT_OK` (SSH 22 inter-zones = DROP)
- JSON Prometheus : `"health":"up"`, `"lastError":""` (scrape HTTPS 9100)

**Phrase de clôture** — *« Le timeout n'est pas une panne : c'est la preuve que la matrice est appliquée. Le health=up prouve que le seul flux Admin→Prod métier (9100) passe, en TLS 1.3 + Basic Auth. »*

---

## 3. Observabilité (2 min)

Passer sur Grafana (déjà ouvert).

1. **Dashboards → M2-Shop → Observabilité Unifiée** — 5 panneaux : req/s, 4xx/5xx, CPU, mémoire, logs bruts.
2. **Explore → Loki**, mode Code :

```
{job="nginx_access"}
```

Puis :

```
{job="nginx_error"}
```

Plage **Last 1 hour**, Run query.

**À dire** — *« Prometheus pour les métriques hôte, Loki pour les logs Nginx. Un seul écran, deux datasources provisionnées par Ansible. Les heures des logs sont en UTC ; Grafana affiche l'heure du navigateur. »*

Si les panneaux sont vides : `vagrant ssh web-prod -c "curl -k -s -o /dev/null https://localhost/"` puis rafraîchir.

---

## 4. Auto-healing — PoC (2 min)

Deux options. **A** si le temps et le réseau le permettent ; **B** si tu ne veux pas recouper Nginx.

### Option A — rejouer le crash (plus fort)

```powershell
vagrant ssh web-prod -c "sudo systemctl stop nginx"
Start-Sleep -Seconds 20
vagrant ssh web-prod -c "sudo systemctl is-active nginx"
vagrant ssh web-prod -c "sudo tail -5 /var/log/healer/remediation.log"
```

**Attendu** : `active` + `Remédiation réussie`.

**À dire** — *« Prometheus scrape toutes les 10 s, Alertmanager pousse NginxDown, le webhook sur web-prod exécute une seule commande sudo : restart nginx. Pas de root partagé. »*

### Option B — preuve déjà horodatée (plus sûr)

```powershell
vagrant ssh web-prod -c "sudo cat /var/log/healer/remediation.log"
vagrant ssh web-prod -c "sudo tail -8 /var/log/healer/webhook-receiver.log"
```

**Preuve du 7 septembre 2026** :

```
21:13:44  NginxDown firing → webhook
21:13:44  code retour=0, HTTP 204
21:13:44  Remédiation réussie
```

Délai < 1 s une fois l'alerte reçue (exigence sujet : < 60 s).

**Phrase de clôture** — *« Le compte healer n'a le droit qu'à systemctl restart nginx.service. C'est de l'automatisation bornée, pas un script root. »*

---

## 5. IaC (30 s – 1 min)

Ouvrir `ansible/site.yml` (4 plays = 4 couches) :

1. `common` — socle toutes VMs  
2. `fw-router` — Jalon A  
3. `web-prod` — prod durcie  
4. `supervision` — collecte / dashboard / alerting  

**À dire** — *« Chaque VM lance ce playbook avec --limit sur elle-même, via ansible_local. On ne pilote pas Ansible depuis Windows : contrainte d'intégration, pas un oubli. vagrant up reconstruit le SI. »*

Montrer en une phrase le `Vagrantfile` : 3 `define`, 2 `intnet` (`net-prod` / `net-admin`).

---

## Si ça dérape

| Symptôme | Recul |
| --- | --- |
| VM down | Option B + captures Grafana déjà faites ; ne pas lancer `vagrant up` |
| Grafana injoignable | `https://127.0.0.1:3443` (pas `http://`) ; `vagrant ssh supervision -c "sudo systemctl is-active grafana"` |
| `health` pas `up` | Vérifier `vagrant ssh fw-router -c "ip -br a"` (eth1/eth2) |
| Crash test encore `inactive` à 20 s | Attendre 15 s de plus ; sinon Option B |
| Jury coupe | Prioriser étapes 2 + 4 : Zero-Trust + healer |

---

## Phrase de fin (15 s)

*« Le PoC valide le cahier des charges : chaque flux de la matrice a un test, le déploiement est de l'infrastructure as code, la recette du 7 septembre le reproduit. Ce n'est pas un SI de production — pas de PKI ni de bastion — mais c'est une architecture supervisée, cloisonnée et rejouable. »*

Documents si le jury demande plus : DAE, `docs/tests-de-validation.md`, `docs/C5.4.1-guide-utilisation-sre.md`.
