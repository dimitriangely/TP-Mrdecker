# TP-Mrdecker — Supervision et Observabilité

Dépôt regroupant l'ensemble des travaux pratiques du module **Supervision / Observabilité**. Chaque séance introduit un outil ou un concept, puis le **Workshop final** les combine dans une architecture sécurisée de type Zero-Trust.

Tous les environnements sont reproductibles via **Vagrant + VirtualBox** et provisionnés par **Ansible** (Infrastructure as Code).

📖 **Glossaire** : définitions des technologies (SNMP, Zabbix, Prometheus, Grafana, InfluxDB) et des termes techniques → [Glossaire/glossaire.md](Glossaire/glossaire.md)

---

## Prérequis communs

| Outil | Version recommandée |
|-------|---------------------|
| [VirtualBox](https://www.virtualbox.org/) | ≥ 6.1 (7.x pour certains TP SNMP) |
| [Vagrant](https://www.vagrantup.com/) | ≥ 2.3 |
| Connexion Internet | Requise au premier `vagrant up` (téléchargement des boxes et paquets) |

**Poste hôte testé :** Windows avec PowerShell. Les commandes Ansible s'exécutent en général **dans les VMs** (`ansible_local`), pas depuis l'hôte.

---

## Parcours pédagogique

```
Séance 1 — SNMP          → Protocole de supervision réseau (v2c, traps, v3)
Séance 2 — Zabbix        → Supervision hybride SNMP + Agent 2
Séance 3 — Prometheus    → Métriques, Grafana, Alertmanager (Flask)
Séance 5 — Prometheus+   → Évolution : FastAPI, ELK, pare-feu, chaos engineering
Séance 6 — InfluxDB v3   → Séries temporelles, SQL, downsampling
Workshop final           → Architecture M2-Shop sécurisée (ANSSI / Zero-Trust)
```

> La séance 4 n'apparaît pas comme dossier distinct : la progression va de la séance 3 à la séance 5, qui approfondit le premier TP Prometheus.

---

## Vue d'ensemble du dépôt

```
TP-Mrdecker/
├── Glossaire/                 # Glossaire des technologies et termes techniques
├── Seance1-SNMP/              # Fondamentaux SNMP (4 TP progressifs)
├── Seance2-Zabbix-SNMP-et-Agent2/
├── Seance3-Prometheus/
├── Seance5-Prometheus-suite/
├── Seance6-InfluxDB/
└── Wokrshop-final/            # Projet de synthèse (observabilité sécurisée)
```

Chaque séance contient en général :
- un **énoncé PDF** ;
- un **Vagrantfile** ;
- des **playbooks / rôles Ansible** ;
- un **README** détaillé avec architecture, commandes et dépannage.

---

## Séance 1 — SNMP (`Seance1-SNMP/`)

**Énoncé :** `Enonce seance 1 - SNMP TPs.pdf`

Introduction au protocole SNMP et à la MIB, du simple agent local jusqu'à SNMPv3 chiffré.

| Dossier | Objectif | Contenu principal |
|---------|----------|-------------------|
| `tp1/` | Agent SNMP + interrogation depuis Windows | `Vagrantfile`, `playbook.yml`, `readme.md`, captures iReasoning MIB Browser |
| `tp2/` | Agent et manager sur une même VM (CLI) | `snmpget`, `snmpwalk`, exploration HOST-RESOURCES-MIB |
| `tp3/` | Architecture distante Manager / Agent | 2 VMs, envoi de **traps** (redémarrage, coupure interface), `CHEATSHEET-SNMP.md` |
| `tp4/` | **SNMPv3** authPriv (SHA + AES) | Sécurisation des échanges, comparaison v2c / v3 par capture de trames |

**Technologies :** `snmpd`, `net-snmp`, communautés SNMPv2c, USM SNMPv3, iReasoning MIB Browser.

**Démarrage type :**
```powershell
cd Seance1-SNMP/tp1   # ou tp2, tp3, tp4
vagrant up
```

---

## Séance 2 — Zabbix SNMP et Agent 2 (`Seance2-Zabbix-SNMP-et-Agent2/`)

**Énoncé :** `Enonce seance 2 - TP Zabbix SNMP et agents 2.pdf`

Déploiement d'une infrastructure Zabbix 7.0 LTS avec collecte **hybride** (SNMP + Zabbix Agent 2).

| VM | IP | Rôle |
|----|-----|------|
| `srv-zabbix` | 192.168.56.10 | Serveur Zabbix, MariaDB, interface web |
| `srv-apache` | 192.168.56.11 | Apache2, SNMPd, Agent 2 |
| `srv-nginx` | 192.168.56.12 | Nginx, SNMPd, Agent 2 |

**Contenu :** `Vagrantfile`, rôles Ansible (`zabbix_server`, `zabbix_agent`, `snmpd`, `apache_web`, `nginx_web`, `common`), `README.md` avec configuration UI, dashboards et tests d'alerte.

**Interface web :** http://localhost:8080/zabbix — `Admin` / `zabbix`

---

## Séance 3 — Prometheus (`Seance3-Prometheus/`)

**Énoncés / livrables :** `Enonce seance 3 - Mise en place de prometheus.pdf`, `Rapport.pdf`

Première stack d'observabilité moderne : modèle **pull**, métriques applicatives et système, alerting.

| VM | IP | Services |
|----|-----|----------|
| `monitoring` | 192.168.56.10 | Prometheus, Grafana, Alertmanager, Node Exporter, API Flask |
| `target` | 192.168.56.20 | Node Exporter |

**Contenu :**
- `app/` — API Flask instrumentée (`prometheus_client`)
- `ansible/` — playbooks, règles d'alerte (`InstanceDown`, `CodeErreurHaut`, `CPUHigh`)
- `README.md` — PromQL, crash-tests, import dashboard Grafana

**Accès :** Prometheus `:9090`, Grafana `:3000`, Flask `:5000`, Alertmanager `:9093`

---

## Séance 5 — Évolution Prometheus + ELK (`Seance5-Prometheus-suite/`)

**Énoncé / livrables :** `Enonce seance 5 - Evolution du premier TP prometheus.pdf`, `Rapport.pdf`

Approfondissement de la séance 3 : API **FastAPI**, stack **ELK** (Elasticsearch, Logstash, Kibana), collecte **pull + push**, pare-feu UFW et scénarios de chaos engineering.

| VM | IP | Services |
|----|-----|----------|
| `cible` | 192.168.56.10 | FastAPI, Node Exporter, Filebeat, UFW |
| `monitoring` | 192.168.56.20 | Prometheus, Grafana, Elasticsearch, Logstash, Kibana |

**Documentation complémentaire :**
- `Explication-fichier-service-systemd-VM1.md`
- `Explication-logstash-conf.md`
- `Explication-règles-parefeu.md`

**Accès :** FastAPI `:5000`, Prometheus `:9090`, Grafana `:3000`, Kibana `:5601`, Elasticsearch `:9200`

> La VM monitoring nécessite **4 Go de RAM** (ELK).

---

## Séance 6 — InfluxDB v3 (`Seance6-InfluxDB/`)

**Énoncé :** `Enonce seance 6 - InfluxDB Implémentation.pdf`

Bases de données de séries temporelles avec **InfluxDB v3 Core**, requêtes SQL, agrégations, haute cardinalité et downsampling.

| Composant | Détail |
|-----------|--------|
| VM `influxdb-lab` | Ubuntu 22.04 — `192.168.56.10` |
| InfluxDB v3 | Port `8086`, stockage Parquet |
| Grafana | Port `3000`, datasource provisionnée |

**Contenu :**
- `ansible/roles/influxdb`, `grafana`, `influxdb_data`
- Scripts : `stress_test.py`, `downsample.py`, jeu de données `data_input.txt`
- `README.md` — requêtes SQL, `date_bin`, data skipping, cron de downsampling

---

## Workshop final — Observabilité sécurisée (`Wokrshop-final/`)

Projet de synthèse inspiré d'un scénario **ANSSI** : architecture **M2-Shop** avec cloisonnement **Zero-Trust**, chiffrement des flux de supervision et stack complète d'observabilité.

### Topologie

```
web-prod (10.0.20.20)  ←→  fw-router  ←→  supervision (10.0.10.5)
   DMZ Production              Routeur              DMZ Admin
```

3 VMs Debian, sans réseau privé direct entre production et supervision : tout transite par `fw-router`.

### Jalons

| Jalon | Contenu |
|-------|---------|
| **A** | Cloisonnement `nftables`, routage statique, matrice de flux |
| **B** | Node Exporter TLS + Basic Auth, Prometheus, Zabbix Agent2 PSK |
| **C+** | Grafana, Loki, Promtail, Alertmanager, dashboards (en cours / à compléter selon avancement) |

### Contenu du dossier

| Élément | Description |
|---------|-------------|
| `Vagrantfile` | 3 VMs, provisioning `ansible_local` par groupe |
| `ansible/` | Rôles `common`, `fw-router`, `web-prod`, `supervision` |
| `ansible/group_vars/all/vault.yml` | Secrets chiffrés (Ansible Vault) |
| `docs/matrice-de-flux.md` | Matrice des flux réseau (DAE Section 1) |
| `docs/tests-de-validation.md` | Protocoles de recette |
| `DAE-*.docx` | Documents d'architecture et plan de continuité |
| `README.md` | Guide détaillé, validations par jalon, gestion du vault |

**Démarrage :**
```bash
cd Wokrshop-final
vagrant up
```

---

## Technologies utilisées

| Domaine | Outils |
|---------|--------|
| Virtualisation | VirtualBox, Vagrant |
| Automatisation | Ansible (rôles, playbooks, Vault) |
| Supervision réseau | SNMP v2c/v3, Zabbix 7, traps |
| Métriques | Prometheus, Node Exporter, `prometheus_client` |
| Visualisation | Grafana |
| Alerting | Alertmanager, triggers Zabbix |
| Logs | Filebeat, Logstash, Elasticsearch, Kibana, Loki, Promtail |
| Applications | Flask, FastAPI (instrumentées) |
| Séries temporelles | InfluxDB v3 Core |
| Sécurité réseau | nftables, UFW, TLS, Basic Auth, PSK Zabbix |

---

## Comment utiliser ce dépôt

1. **Suivre l'ordre des séances** pour une progression logique (SNMP → Zabbix → Prometheus → ELK → InfluxDB → Workshop).
2. **Lire le README de chaque séance** avant `vagrant up` : prérequis, IPs et ports diffèrent.
3. **Ne lancer qu'une séance à la fois** : les VMs partagent souvent le réseau `192.168.56.0/24` ou des ressources VirtualBox.
4. **Consulter les PDF d'énoncé** pour le contexte pédagogique et les critères de réussite.
5. **Workshop final** : méthode couche par couche, validation à chaque jalon (voir `Wokrshop-final/README.md`).

### Commandes Vagrant utiles

```powershell
vagrant up              # Créer et provisionner les VMs
vagrant ssh <nom-vm>    # Connexion SSH
vagrant provision       # Rejouer Ansible sans redémarrer
vagrant halt            # Arrêter les VMs
vagrant destroy -f      # Supprimer complètement l'environnement
```

---

## Documentation par séance

| Ressource | Fichier |
|-----------|---------|
| Glossaire (technologies et termes) | [Glossaire/glossaire.md](Glossaire/glossaire.md) |

| Séance | README principal |
|--------|------------------|
| SNMP tp1–tp4 | `Seance1-SNMP/tp*/readme.md` |
| Zabbix | `Seance2-Zabbix-SNMP-et-Agent2/README.md` |
| Prometheus | `Seance3-Prometheus/README.md` |
| Prometheus + ELK | `Seance5-Prometheus-suite/README.md` |
| InfluxDB | `Seance6-InfluxDB/README.md` |
| Workshop final | `Wokrshop-final/README.md` |

---

## Contexte

Travaux pratiques réalisés dans le cadre du module de supervision (TP Mr Decker).  
Environnements de laboratoire : **ne pas réutiliser les mots de passe par défaut en production**.
