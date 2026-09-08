# Fiches orales — Dossier de soutenance Bloc 5

Document **à lire à voix haute**. Les longs fichiers (`DAE`, `tests-de-validation.md`, etc.) restent dans `docs/` si le jury creuse.

**Phrase d'ouverture :** *« M2-Shop est une boutique web. Le PoC montre une observabilité compatible Zero-Trust : 3 zones, 4 flux, IaC, recette rejouée le 7 septembre. »*

**Phrase de clôture :** *« Chaque flux a un test, le déploiement est IaC, la recette du 7 septembre le reproduit. Ce n'est pas de la prod : pas de PKI, pas de bastion, pas de backup — le PRA c'est reconstruire. »*

---

# 1. Grille Bloc 5 — où répondre

| On me demande… | Je montre / je dis | Page Word |
| --- | --- | --- |
| C5.1.1 Existant | Avant = LAN plat. Après = 3 zones | § 2 |
| C5.1.2 Contraintes | ANSSI, Windows, pas de backup | § 2 |
| C5.1.3 Cahier des charges | 4 flux FORWARD + 2 plans | § 3 |
| C5.2.1 Architecture | Schéma HLD + LLD (IPs, ports) | § 3 |
| C5.2.2 Recette | Commande → attendu | § 4 |
| C5.2.3 PoC | Démo 5–7 min | § 7 |
| C5.3.1 Intégration | `ansible_local` + `--limit` | § 5 |
| C5.3.2 Automatisation | Playbooks + `healer` | § 5 |
| C5.3.3 Compte-rendu | Tableau du 7 sept. | § 4 |
| C5.4.1 Guide | Grafana + interdits | § 6 |

---

# 2. Existant et contraintes (C5.1.1 / C5.1.2)

## Avant

- Boutique sur un LAN plat, admin et prod mélangées.
- Pas de matrice de flux, collecteurs souvent en clair.
- Zabbix souvent **passif** (le serveur initie vers la prod).
- Panne Nginx = un humain en root.
- Reconstruction à la main.

## Après (cible)

```
web-prod 10.0.20.20  ←→  fw-router .20.1 / .10.1  ←→  supervision 10.0.10.5
DMZ Prod                  DROP + 4 flux                    DMZ Admin
```

Aucun réseau commun prod/admin. Le SRE pilote depuis Windows (`vagrant ssh`, Grafana `:3443`).

## Contraintes (à citer)

- **ANSSI** : DROP, moindre privilège, preuve de refus (timeout 22).
- **Métier** : le site 80/443 reste public, **hors** le routeur.
- **RTO Nginx** : < 60 s → mesuré **< 1 s** le 7 sept. à 21:13:44 UTC.
- **Technique** : pas d'Ansible sur Windows → `ansible_local` dans chaque VM.
- **Routes statiques** obligatoires (sinon le NAT VirtualBox, Zero-Trust inopérant).
- **Limites assumées** : HTTP sur 9095 et Loki ; Grafana `admin`/`admin` ; **pas de backup** (on reconstruit).

---

# 3. Architecture et flux (C5.1.3 / C5.2.1)

**HLD** = 3 zones + 4 flèches. **LLD** = IPs, ports, services, fichiers (détail en Partie B).

![Schéma d'architecture M2-Shop — 3 zones cloisonnées](docs/architecture-m2shop.png)

## Qui fait quoi

| VM | IP | Rôle |
| --- | --- | --- |
| web-prod | 10.0.20.20 | Nginx, Node Exporter, Zabbix Agent, Promtail, healer |
| fw-router | .20.1 / .10.1 | Seul routeur, nftables DROP |
| supervision | 10.0.10.5 | Prometheus, Loki, Grafana, Zabbix, Alertmanager |

## 4 flux FORWARD seulement

| Sens | Port | Usage | Chiffrement |
| --- | --- | --- | --- |
| Admin → Prod | 9100 | Prometheus scrape | TLS 1.3 + bcrypt |
| Prod → Admin | 10051 | Zabbix **push** | PSK |
| Prod → Admin | 3100 | Promtail → Loki | HTTP (labo) |
| Admin → Prod | 9095 | Auto-healing | HTTP (labo) |

## Deux plans (ne pas les mélanger)

- **FORWARD** = uniquement le tableau ci-dessus.
- **Hôte** = SSH 22, DNS, site 80/443, Grafana 3000. Ça **ne traverse pas** fw-router.

## Phrases utiles

- *« Zabbix n'initie jamais vers la prod. »*
- *« SSH inter-zones timeout : c'est voulu. »*
- *« Sur supervision, 10051 et 3100 n'acceptent que 10.0.20.20 — même si le routeur est contourné. »*
- *« fw-router n'est pas la gateway par défaut : routes systemd. »*

---

# 4. Recette et CR du 7 septembre (C5.2.2 / C5.3.3)

Un test = **commande + attendu + obtenu**. Pas besoin de tout relire.

| Jalon | Test | Obtenu le 7 sept. |
| --- | --- | --- |
| A | `ip -br a` | eth1/eth2 = IPs du DAT |
| A | Routes | via `.20.1` / via `.10.1` |
| A | SSH 22 inter-zones | **TIMEOUT_OK** |
| B | metrics sans auth | **401** |
| B | Prometheus | **health=up** |
| B | Zabbix | heartbeat **working again** 20:09 |
| C | Loki | `nginx_access` + `nginx_error` |
| C | Grafana | dashboard M2-Shop + Explore |
| D | Préchecks | healer = 1 commande sudo ; services active |
| D | Crash Nginx | **21:13:44** firing → 204 → relancé **même seconde** |

Si on me demande la commande : elles sont dans `docs/tests-de-validation.md`. Ici je donne le **résultat**.

---

# 5. Intégration et automatisation (C5.3.1 / C5.3.2)

## Pourquoi `ansible_local`

- Hôte Windows : pas d'orchestrateur.
- Vault hors partage `/vagrant` (sinon Ansible exécute le fichier mot de passe).
- `--limit` : chaque VM ne configure **qu'elle-même** (respecte le cloisonnement).

## 4 couches = `site.yml`

1. `common` — socle  
2. `fw-router` — Jalon A  
3. `web-prod` — prod  
4. `supervision` — collecte / alertes  

## Automatisation

- Vagrant = les 3 VMs et les 2 `intnet`.
- Ansible = nftables, TLS, Grafana, Zabbix…
- systemd = routes + services après reboot.
- `healer` = **une** commande : `systemctl restart nginx.service`.

**Pas automatisé (à dire)** : bump OpenSSL si bug PSK ; pas de job de sauvegarde.

---

# 6. Guide SRE (C5.4.1)

## Usage quotidien

- Grafana : `https://127.0.0.1:3443` — `admin` / `admin` — dossier **M2-Shop**.
- Explore Loki : `{job="nginx_access"}` ou `{job="nginx_error"}`.
- Logs VM en **UTC** ; Grafana en heure Paris (UTC+2).

## Interdits (pièges oraux)

| Ne pas faire | Pourquoi |
| --- | --- |
| `curl https://10.0.20.20/` depuis Admin | 443 n'est pas en FORWARD |
| SSH prod → admin (port 22) | DROP |
| `scp` vers 10.0.10.5 | 22 interdit |
| Hostname `fw-router` | Noms : `fw-router-prod` / `fw-router-admin` |

Admin SSH = **`vagrant ssh`** depuis Windows.

## Incident (PCO en 4 phrases)

1. Confirmer via Grafana / Slack / Prometheus — pas un curl 443.
2. DROP FORWARD sur 10.0.20.20 (`vagrant ssh fw-router`).
3. Preuves dans **`/vagrant`**.
4. Silence Alertmanager en **localhost** sur supervision.

## Backup

Pas de dump. Détruire une VM = perdre l'historique. On **`vagrant up`**. Git = seule sauvegarde de l'état voulu.

---

# 7. Démo 5–7 min (C5.2.3)

**Avant d'entrer :** `vagrant status` = 3 × running. Grafana déjà ouvert. Ne pas lancer `vagrant up` devant le jury.

| Min | Je fais | Je dis |
| --- | --- | --- |
| 0–1 | `vagrant status` + `ip -br a` sur fw-router | 3 zones, eth1 prod, eth2 admin |
| 1–2 | timeout 22 puis targets Prometheus | DROP vs flux 9100 `up` |
| 2–4 | Dashboard M2-Shop + Explore Loki | Métriques + logs, 2 datasources |
| 4–6 | Logs healer **ou** `stop nginx` + 20 s | 21:13:44, une commande sudo |
| 6–7 | Ouvrir `ansible/site.yml` | 4 plays, `ansible_local`, pas depuis Windows |

**Plan B** si une VM est down : montrer `remediation.log` (21:13:44) + captures Grafana, ne pas reconstruire.

**Crash live (option A) :**

```powershell
vagrant ssh web-prod -c "sudo systemctl stop nginx"
Start-Sleep -Seconds 20
vagrant ssh web-prod -c "sudo systemctl is-active nginx"
```

Attendu : `active`.

---

# 8. Questions pièges — réponses courtes

| Question | Réponse |
| --- | --- |
| C'est de la prod ? | Non. PoC pédagogique. HTTP webhook/Loki, admin/admin, pas de backup. |
| Pourquoi HTTP 9095 ? | Labo `intnet`. En prod : mTLS. Écart écrit dans le DAT. |
| Pourquoi pas de backup ? | Cadre TP. PRA = IaC. En prod : dump MariaDB + Grafana + Loki. |
| Et si fw-router tombe ? | Toute la supervision inter-zones tombe. Mono-instance assumé. |
| Guest Additions 6 vs VBox 7 ? | Warning. `/vagrant` a monté. Non bloquant. |
| Zabbix erreurs au boot ? | Normal : web-prod démarre avant supervision. Puis `working again`. |
| 404 dans error.log ? | Non. 404 = access.log. error.log = notices Nginx / ligne test. |

---

# 9. Commandes à avoir sous les yeux

```powershell
vagrant status
vagrant ssh fw-router -c "ip -br a"
vagrant ssh web-prod -c "timeout 5 nc -zv 10.0.10.5 22 || echo TIMEOUT_OK"
vagrant ssh supervision -c "curl -s http://localhost:9090/api/v1/targets"
vagrant ssh web-prod -c "sudo tail -5 /var/log/healer/remediation.log"
```

Grafana : `https://127.0.0.1:3443` (pas `http://`).
