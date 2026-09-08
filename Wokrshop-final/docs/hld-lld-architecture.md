# HLD, LLD et schéma d'architecture

**C5.2.1** — concevoir l'architecture (vue haute et vue basse).  
**C5.1.3** — le HLD reprend le cahier des charges ; le LLD le rend implémentable.

- **HLD** (*High Level Design*) : zones, acteurs, flux métier, frontières de confiance. On s'adresse au jury / RSSI / métier.
- **LLD** (*Low Level Design*) : IPs, ports, services, fichiers, unités systemd. On s'adresse à l'intégrateur.

Le schéma ci-dessous est la **figure d'architecture** à projeter ou à ouvrir dans le Word.

![Schéma d'architecture M2-Shop — 3 zones cloisonnées](docs/architecture-m2shop.png)

*Figure — HLD : DMZ Production, pare-feu inter-zones, DMZ Administration. Les flèches numérotées sont les seuls flux FORWARD.*

---

## 1. HLD — High Level Design

### 1.1 Objectif

Rendre une boutique web (M2-Shop) **observable** sans ouvrir la production à l'administration. La supervision est une zone de confiance distincte. Tout échange inter-zones est explicite, journalisé, et testé.

### 1.2 Acteurs

| Acteur | Zone | Intention |
| --- | --- | --- |
| Client Internet | Public | Consulter le site HTTPS |
| SRE | Hôte Windows | Piloter, voir Grafana, SSH Vagrant (NAT) |
| Services prod | DMZ Prod | Servir le site, pousser métriques/logs, s'auto-réparer |
| Plateforme admin | DMZ Admin | Collecter, alerter, dashboarder |
| Pare-feu | Inter-zones | Autoriser 4 flux, dropper le reste |

### 1.3 Découpage en zones (modèle de confiance)

| Zone | Confiance | Contenu |
| --- | --- | --- |
| Internet | Non fiable | Clients du site |
| DMZ Production | Métier exposé | Nginx + collecteurs durcis |
| Inter-zones | Point de contrôle unique | fw-router (nftables DROP) |
| DMZ Admin | Supervision | Prometheus, Loki, Grafana, Zabbix, Alertmanager |
| Hôte SRE | Poste d'exploitation | Pas de playbook distant, pas de réseau commun prod/admin |

Il n'existe **aucun** LAN partagé entre web-prod et supervision (`intnet` `net-prod` ≠ `net-admin`).

### 1.4 Flux métier (niveau HLD)

1. **Clients → Nginx** : HTTP redirigé vers HTTPS. N'emprunte **pas** fw-router.
2. **Prometheus → Node Exporter** : scrape PULL chiffré (Admin → Prod).
3. **Zabbix Agent → Zabbix Server** : push PSK (Prod → Admin). Le serveur n'initie jamais.
4. **Promtail → Loki** : centralisation des logs Nginx (Prod → Admin).
5. **Alertmanager → healer** : remédiation Nginx (Admin → Prod).
6. **SRE → Grafana** : HTTPS via port-forward `127.0.0.1:3443` (plan hôte).

### 1.5 Principes HLD

- Politique **deny by default** sur FORWARD et sur chaque hôte.
- **Défense en profondeur** : même si fw-router est contourné, Loki/Zabbix n'acceptent que `10.0.20.20`.
- **IaC** : l'architecture est le `Vagrantfile` + `ansible/site.yml`, pas un dessin orphelin.
- **PRA** : reconstruction, pas de restore (hors périmètre backup).

---

## 2. LLD — Low Level Design

### 2.1 Adressage et interfaces

| Hôte | Interface | Réseau | IP |
| --- | --- | --- | --- |
| web-prod | eth0 | NAT VirtualBox | 10.0.2.15 |
| web-prod | eth1 | `net-prod` | 10.0.20.20/24 |
| fw-router | eth0 | NAT | 10.0.2.15 |
| fw-router | eth1 | `net-prod` | 10.0.20.1/24 |
| fw-router | eth2 | `net-admin` | 10.0.10.1/24 |
| supervision | eth0 | NAT | 10.0.2.15 |
| supervision | eth1 | `net-admin` | 10.0.10.5/24 |

Routes (systemd) :

- web-prod : `10.0.10.0/24 via 10.0.20.1 dev eth1`
- supervision : `10.0.20.0/24 via 10.0.10.1 dev eth1`

### 2.2 Matrice FORWARD (LLD)

| # | Source | Dest | Proto | Port | Initiation | Contrôle |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 10.0.10.5 | 10.0.20.20 | TCP | 9100 | Admin | TLS 1.3 + Basic Auth bcrypt |
| 2 | 10.0.20.20 | 10.0.10.5 | TCP | 10051 | Prod | TLS-PSK, identité `PSK_WEBPROD_001` |
| 3 | 10.0.20.20 | 10.0.10.5 | TCP | 3100 | Prod | HTTP Promtail → Loki |
| 4 | 10.0.10.5 | 10.0.20.20 | TCP | 9095 | Admin | HTTP `POST /alert` |

Hors FORWARD : SSH 22 (NAT), DNS 53, Nginx 80/443 (INPUT web-prod), Grafana 3000 (INPUT supervision).

### 2.3 Composants et versions

| Composant | Hôte | Version / écoute | Unité |
| --- | --- | --- | --- |
| Nginx | web-prod | 80 → 443, TLS auto-signé | `nginx.service` |
| Node Exporter | web-prod | 1.8.2, `:9100` TLS 1.3 | `node_exporter.service` |
| Zabbix Agent2 | web-prod | 7.0, push | `zabbix-agent2.service` |
| Promtail | web-prod | 3.5.1 → `:3100` | `promtail.service` |
| webhook-receiver | web-prod | `:9095` | `webhook-receiver.service` |
| nftables + ip_forward | fw-router | `/etc/nftables.conf` | `nftables.service` |
| Prometheus | supervision | 2.55.1, `:9090` | `prometheus.service` |
| Alertmanager | supervision | 0.27.0, `:9093` localhost | `alertmanager.service` |
| Zabbix Server + MariaDB | supervision | 7.0, `:10051` | `zabbix-server` |
| Loki | supervision | 3.5.1, `:3100` | `loki.service` |
| Grafana | supervision | 13.1.0, `:3000` HTTPS | `grafana.service` |

### 2.4 Fichiers et comptes clés

| Élément | Chemin / compte |
| --- | --- |
| Playbook | `ansible/site.yml` (4 rôles) |
| nftables routeur | `roles/fw-router/templates/nftables-router.conf.j2` |
| nftables hôtes | `nftables-webprod.conf.j2`, `nftables-supervision.conf.j2` |
| Sudoers healer | `/etc/sudoers.d/supervision` — une commande |
| Script remédiation | `/usr/local/bin/restart-nginx.sh` |
| Logs healer | `/var/log/healer/remediation.log` |
| Vault | `/etc/ansible-vault-pass.txt` (hors `/vagrant`) |

### 2.5 Chaîne d'alerte (LLD)

```
nginx.service down
  → Node Exporter (collector systemd, scrape 10 s)
  → règle Prometheus NginxDown (for: 0s)
  → Alertmanager (group_wait 5 s)
       ├─ Slack #alertes-m2shop
       └─ POST http://10.0.20.20:9095/alert
            → healer : systemctl restart nginx.service
```

Validé le 7 septembre 2026 à 21:13:44 UTC (< 1 s une fois l'alerte reçue).

---

## 3. Traceabilité HLD → LLD → code

| Décision HLD | Traduction LLD | Preuve |
| --- | --- | --- |
| 2 DMZ sans LAN commun | 2 `intnet` Vagrant | `Vagrantfile` |
| Point de contrôle unique | fw-router FORWARD DROP + 4 accept | `nftables-router.conf.j2` |
| Zabbix ne « tire » pas | Agent `ServerActive`, pas de FORWARD 10050 | `zabbix_agent2.conf.j2` |
| Collecteurs bornés | `saddr 10.0.20.20` sur 10051/3100 | `nftables-supervision.conf.j2` |
| Remédiation non-root | sudoers chirurgical | `sudoers-supervision.j2` |
| Rejouable | `ansible_local` `--limit` | `site.yml` |
