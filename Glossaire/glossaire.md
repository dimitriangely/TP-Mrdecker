# Glossaire — TP-Mrdecker

Référence des **technologies** et **termes techniques** rencontrés dans l'ensemble des travaux pratiques (SNMP, Zabbix, Prometheus, ELK, InfluxDB, Workshop final).

Les entrées sont classées par thème. Les termes en **gras** dans une définition renvoient à d'autres entrées du glossaire.

---

## Table des matières

0. [Technologies principales](#technologies-principales--vue-densemble)
1. [Infrastructure et automatisation](#1-infrastructure-et-automatisation)
2. [Réseau et sécurité](#2-réseau-et-sécurité)
3. [SNMP et supervision réseau](#3-snmp-et-supervision-réseau)
4. [Zabbix](#4-zabbix)
5. [Observabilité — métriques (Prometheus)](#5-observabilité--métriques-prometheus)
6. [Observabilité — logs (ELK, Loki)](#6-observabilité--logs-elk-loki)
7. [Séries temporelles (InfluxDB)](#7-séries-temporelles-influxdb)
8. [Applications et instrumentation](#8-applications-et-instrumentation)
9. [Concepts transversaux](#9-concepts-transversaux)
10. [Index alphabétique rapide](#index-alphabétique-rapide)

---

## Technologies principales — Vue d'ensemble

Cette section présente les cinq piliers technologiques du parcours TP-Mrdecker. Les termes plus fins (OID, PromQL, trigger, WAL, etc.) sont détaillés dans les sections thématiques ci-dessous.

### SNMP (Simple Network Management Protocol)

**SNMP** est un protocole standard de supervision réseau, défini par l'IETF, utilisé depuis les années 1980 pour interroger et administrer à distance des équipements (serveurs, switchs, imprimantes, etc.).

Il fonctionne selon un modèle **agent / manager** :
- l'**agent** (`snmpd`) tourne sur la machine supervisée et expose des informations via une arborescence d'objets (**MIB**, identifiés par des **OID**) ;
- le **manager** interroge l'agent (`snmpget`, `snmpwalk`) ou reçoit des alertes asynchrones (**traps**) sur des événements (redémarrage, panne d'interface).

Les échanges utilisent principalement **UDP** : port **161** pour les requêtes, port **162** pour les traps.

Trois grandes versions sont vues dans les TP :
- **SNMPv1 / v2c** : authentification par **communauté** (chaîne partagée, souvent en clair) ;
- **SNMPv3** : authentification (**SHA**) et chiffrement (**AES**) via le modèle **USM**, adapté à un contexte sécurisé.

SNMP reste très répandu pour la supervision « réseau et matériel ». Dans ce dépôt, il est utilisé des TP 1 à 4 (fondamentaux, traps, sécurisation v3), puis en complément de **Zabbix** (séance 2) pour collecter des métriques via les templates « Linux by SNMP ».

---

### Zabbix

**Zabbix** est une plateforme open source de **supervision d'infrastructure** (serveurs, services, réseau, applications). Elle centralise la collecte, le stockage historique, l'alerting et la visualisation dans une interface web unique.

Architecture typique :
- **Zabbix Server** : moteur central qui planifie la collecte, évalue les règles d'alerte et stocke les données ;
- **base de données** (**MariaDB** dans les TP) : configuration, historique des métriques et des événements ;
- **agents** (**Zabbix Agent 2**) et/ou **SNMP** : collecte sur les machines supervisées ;
- **templates** : modèles réutilisables d'items, graphiques et **triggers** (règles d'alerte).

Zabbix supporte plusieurs modes de collecte :
- **passif** : le serveur interroge l'agent (pull) ;
- **actif** : l'agent envoie les données au serveur (push) — mode imposé dans le workshop final pour respecter le cloisonnement réseau.

Points forts : richesse des templates intégrés, cartographie réseau (Network Map), dashboards, seuils et notifications. Dans ce dépôt : déploiement complet en séance 2 (Apache + Nginx + SNMP hybride), puis Zabbix Agent2 chiffré en **PSK** dans le workshop final.

---

### Prometheus

**Prometheus** est un système open source de **monitoring et d'alerting** orienté **métriques** (séries temporelles numériques), maintenu par la CNCF. Il est devenu un standard de l'**observabilité** moderne, en complément ou en alternative à des outils comme Zabbix pour les métriques.

Principe fondamental — modèle **pull** : Prometheus interroge périodiquement (par défaut toutes les 15 secondes) les endpoints HTTP `/metrics` de ses **cibles** (applications instrumentées, **Node Exporter**, etc.). Si une cible ne répond plus, l'alerte `up == 0` se déclenche naturellement.

Composants clés :
- **Prometheus Server** : stockage des séries temporelles, moteur de requêtes **PromQL**, évaluation des règles d'alerte ;
- **exporters** (ex. **Node Exporter**) : agents exposant des métriques système au format Prometheus ;
- **Alertmanager** : routage et notification des alertes (Slack, webhook, email).

Les métriques sont typiquement des **counters** (valeurs croissantes), **gauges** ou **histogrammes** (distributions de latence). Le code applicatif (Flask, FastAPI) peut être **instrumenté** via `prometheus_client`.

Dans ce dépôt : stack complète en séance 3 (Flask + Grafana + Alertmanager), enrichie en séance 5 (FastAPI + ELK + chaos engineering), puis déployée de façon sécurisée (TLS + Basic Auth) dans le workshop final.

---

### Grafana

**Grafana** est une plateforme open source de **visualisation et d'exploration de données**. Elle ne collecte pas les métriques elle-même : elle se connecte à des **datasources** (Prometheus, InfluxDB, Loki, Elasticsearch, etc.) pour afficher graphiques, jauges, tableaux et **dashboards**.

Fonctionnalités principales :
- création et import de **dashboards** (JSON) ;
- requêtes interactives (PromQL pour Prometheus, SQL pour InfluxDB, LogQL pour Loki) ;
- **provisioning** automatique des datasources et dashboards via fichiers YAML (utilisé dans tous les TP Ansible) ;
- alertes Grafana (complémentaires aux alertes Prometheus/Zabbix).

Grafana agrège en un seul endroit des données issues de sources hétérogènes. Dans ce dépôt : visualisation des métriques Prometheus (séances 3 et 5), des données InfluxDB (séance 6), et un dashboard unifié M2-Shop combinant métriques Prometheus et logs Loki (workshop final).

Identifiants courants en lab : `admin` / `admin` ou `admin123`.

---

### InfluxDB

**InfluxDB** est une **base de données de séries temporelles** (Time Series Database) conçue pour stocker et interroger d'importants volumes de mesures horodatées : capteurs industriels, métriques IoT, monitoring applicatif, analytics.

Les données sont organisées en :
- **measurements** (tables logiques, ex. `flux_production`) ;
- **tags** (dimensions de filtrage : `ligne_id`, `operateur`) ;
- **fields** (valeurs mesurées : `temperature`, `vitesse`) ;
- **timestamp** (horodatage de chaque point).

Écriture : format **Line Protocol** via API HTTP. Lecture : requêtes **SQL** (à partir de la v3).

**InfluxDB v3 Core** (séance 6) marque une évolution majeure :
- stockage columnar **Parquet** sur disque (au lieu d'un index en RAM) ;
- tolérance à la **haute cardinalité** (millions de tags uniques sans explosion mémoire) ;
- pipeline **WAL** → Parquet avec architecture **hot/cold** ;
- optimisations de requête (**data skipping**, `date_bin`, `EXPLAIN`).

InfluxDB se distingue de **Prometheus** : Prometheus excelle sur le monitoring infra temps réel et l'alerting pull ; InfluxDB cible plutôt le stockage analytique long terme, l'agrégation (**downsampling**) et les requêtes SQL complexes sur de gros volumes historiques. **Grafana** sert de couche de visualisation commune aux deux.

---

## 1. Infrastructure et automatisation

### Ansible
Outil d'automatisation et de configuration. Dans ces TP, il déploie paquets, fichiers de configuration et services sur les VMs via des **playbooks** et des **rôles**. Exécuté en `ansible_local` depuis Vagrant (Ansible tourne dans la VM invitée).

### Ansible Vault
Mécanisme de chiffrement Ansible pour stocker des secrets (mots de passe, clés) dans des fichiers YAML (`vault.yml`). Le déchiffrement nécessite un mot de passe vault, déposé sur les VMs du workshop final.

### ansible_local
Provisioner Vagrant qui installe et exécute Ansible **à l'intérieur** de la VM, plutôt que depuis l'hôte Windows. Évite les problèmes de chemins, de permissions et de connectivité SSH depuis l'extérieur.

### Box (Vagrant)
Image de machine virtuelle pré-packagée (ex. `ubuntu/focal64`, `debian/bookworm64`) téléchargée depuis Vagrant Cloud au premier `vagrant up`.

### Handler (Ansible)
Tâche déclenchée uniquement si une autre tâche a modifié l'état du système (ex. redémarrer un service après changement de configuration). Évite les redémarrages inutiles.

### Infrastructure as Code (IaC)
Pratique consistant à décrire l'infrastructure (VMs, réseau, services) dans des fichiers versionnés (`Vagrantfile`, playbooks Ansible) plutôt que par configuration manuelle.

### Inventory (Ansible)
Fichier listant les hôtes cibles et leurs groupes (`hosts.ini`). Permet d'appliquer un playbook à un sous-ensemble de machines (`web-prod`, `supervision`, etc.).

### Playbook (Ansible)
Fichier YAML décrivant une séquence de tâches à exécuter sur un ou plusieurs hôtes (ex. `playbook-monitoring.yml`, `site.yml`).

### Provisioning
Phase post-création d'une VM où Vagrant exécute des scripts ou Ansible pour installer et configurer l'environnement.

### Rôle (Ansible)
Module réutilisable regroupant tâches, templates, variables et handlers pour un composant précis (ex. `node_exporter`, `zabbix_server`, `nftables`).

### systemd
Gestionnaire de services et d'unités sous Linux. Les applications (Flask, FastAPI, Prometheus, etc.) sont déclarées via des fichiers `.service` et gérées par `systemctl`.

### Template Jinja2 (`.j2`)
Fichier modèle Ansible avec variables (`{{ variable }}`) rendu en fichier de configuration final sur la cible (ex. `prometheus.yml.j2`, `nftables-router.conf.j2`).

### Vagrant
Outil en ligne de commande pour créer, configurer et gérer des machines virtuelles de façon reproductible via un `Vagrantfile`.

### Vagrantfile
Fichier Ruby décrivant les VMs (box, RAM, réseau, provisioners) et leurs paramètres.

### VirtualBox
Hyperviseur de type 2 utilisé comme backend de virtualisation pour tous les environnements de laboratoire.

### VM (Machine virtuelle)
Environnement Linux isolé simulant un serveur (Ubuntu, Debian). Chaque séance utilise une ou plusieurs VMs interconnectées.

---

## 2. Réseau et sécurité

### Basic Auth (authentification HTTP de base)
Mécanisme HTTP envoyant identifiant et mot de passe encodés en Base64. Utilisé sur **Node Exporter** (workshop) pour protéger l'endpoint `/metrics` en complément du **TLS**.

### bcrypt
Algorithme de hachage de mots de passe. Dans le workshop, le hash bcrypt du mot de passe Basic Auth est généré dynamiquement par Ansible pour `web-config.yml` de Node Exporter.

### Certificat auto-signé
Certificat TLS créé localement, non signé par une autorité reconnue. Utilisé en lab ; Prometheus utilise `insecure_skip_verify` pour accepter ces certificats lors du scrape HTTPS.

### DMZ (Zone démilitarisée)
Segment réseau isolé exposant des services (production ou administration). Dans le workshop : `DMZ Prod` (web-prod) et `DMZ Admin` (supervision), séparées par un routeur-pare-feu.

### Défense en profondeur
Stratégie de sécurité multicouche : pare-feu sur le routeur **et** sur chaque VM (`nftables`), en plus du chiffrement des flux de supervision.

### FORWARD (nftables)
Chaîne de filtrage des paquets qui traversent la machine (routage). Le `fw-router` autorise uniquement les ports explicitement listés dans la matrice de flux.

### Handshake TLS
Négociation initiale d'une connexion chiffrée (version TLS, algorithmes, échange de clés). Observé via `tcpdump` pour valider TLS 1.3 ou TLS-PSK Zabbix.

### Host-only (réseau privé VirtualBox)
Interface réseau isolée entre l'hôte et les VMs (ex. `192.168.56.0/24`). Les VMs communiquent entre elles sans être exposées sur le réseau physique.

### Matrice de flux
Tableau documentant chaque flux réseau autorisé : source, destination, protocole, port, sens d'initiation et justification. Base du DAE (Section 1) du workshop.

### nftables
Framework moderne de filtrage et de routage sous Linux (successeur d'iptables). Utilisé pour le cloisonnement Zero-Trust du workshop.

### Pare-feu
Dispositif ou règles logicielles filtrant le trafic réseau selon IP, port et protocole. Implémenté via **nftables** (workshop) ou **UFW** (séance 5).

### PSK (Pre-Shared Key)
Clé secrète partagée à l'avance entre deux parties. Dans Zabbix Agent2, la PSK (64 caractères hex) chiffre les communications agent → serveur en mode actif.

### Routage statique
Table de routes configurée manuellement (via `ip route` ou service systemd) pour diriger le trafic inter-zones vers `fw-router`, sans protocole dynamique (OSPF, BGP).

### TLS (Transport Layer Security)
Protocole de chiffrement des communications (successeur de SSL). TLS 1.3 est imposé sur Node Exporter et Grafana dans le workshop.

### tcpdump
Outil en ligne de commande capturant le trafic réseau. Utilisé pour prouver le chiffrement SNMPv3, Zabbix PSK ou l'absence de données en clair.

### Timeout vs refus de connexion
- **Timeout** : aucune réponse (paquets bloqués/droppés) → preuve qu'un port est interdit.
- **Refus (RST)** : le port est autorisé au niveau pare-feu mais aucun service n'écoute → preuve que le flux traverse le routeur.

### UFW (Uncomplicated Firewall)
Interface simplifiée au-dessus d'iptables. Dans la séance 5, elle restreint les ports ouverts sur la VM cible (FastAPI, Node Exporter, Filebeat).

### Zero-Trust
Modèle de sécurité où aucun flux n'est implicitement autorisé : chaque communication est explicitement permise, chiffrée et justifiée. Aucun accès direct entre production et supervision sans passer par le routeur.

---

## 3. SNMP et supervision réseau

### Agent SNMP (`snmpd`)
Démon sur la machine supervisée qui expose des informations système via le protocole SNMP (port UDP 161).

### AES (Advanced Encryption Standard)
Algorithme de chiffrement symétrique. En SNMPv3 **authPriv**, il chiffre le contenu des PDU (niveau `priv`).

### authNoPriv / authPriv / noAuthNoPriv
Niveaux de sécurité SNMPv3 :
- `noAuthNoPriv` : ni authentification ni chiffrement ;
- `authNoPriv` : authentification SHA, données en clair ;
- `authPriv` : authentification + chiffrement AES (recommandé).

### Communauté SNMP
Chaîne de caractères servant de mot de passe en SNMPv1/v2c (ex. `public`, `tp_admin`). Lecture seule (`rocommunity`) ou lecture-écriture (`rwcommunity`).

### HOST-RESOURCES-MIB
MIB standard décrivant les ressources hôte : mémoire, stockage, processeurs, logiciels installés.

### IF-MIB
MIB standard des interfaces réseau (`ifDescr`, `ifOperStatus`, etc.). Utilisée pour détecter une coupure d'interface (trap dans tp3).

### iReasoning MIB Browser
Client graphique Windows pour interroger un agent SNMP, parcourir la **MIB** et lire des **OID** (tp1).

### Manager SNMP
Entité qui interroge les agents (`snmpget`, `snmpwalk`) ou reçoit des traps (`snmptrapd`). Peut être sur la même machine que l'agent (tp2) ou distante (tp3/tp4).

### MIB (Management Information Base)
Arborescence hiérarchique d'objets supervisables, chacun identifié par un **OID**. Ex. : `SNMPv2-MIB`, `IF-MIB`.

### net-snmp
Suite d'outils et de bibliothèques SNMP sous Linux (`snmpget`, `snmpwalk`, `snmptrap`, `snmpd`).

### OID (Object Identifier)
Identifiant unique d'un objet SNMP (ex. `1.3.6.1.2.1.1.5.0` = `sysName`). Peut être numérique ou symbolique (`SNMPv2-MIB::sysName.0`).

### PDU (Protocol Data Unit)
Unité de données échangée dans un message SNMP (GET, SET, TRAP, etc.).

### SHA (Secure Hash Algorithm)
Algorithme d'authentification utilisé en SNMPv3 pour vérifier l'intégrité et l'origine des messages (`auth`).

### snmpget
Commande lisant la valeur d'un OID précis sur un agent.

### snmp-mibs-downloader
Paquet Debian téléchargeant les MIB standard IETF pour permettre la résolution symbolique des OID.

### snmptrap / Trap SNMP
Message **asynchrone** envoyé par l'agent vers le manager (port UDP 162) lors d'un événement (redémarrage, panne interface), sans requête préalable du manager.

### snmptrapd
Démon recevant et journalisant les traps SNMP sur le manager.

### snmptranslate
Outil convertissant entre noms symboliques MIB et OID numériques, ou affichant la description d'un OID.

### snmpwalk
Commande parcourant récursivement une branche de la MIB et retournant toutes les valeurs.

### SNMPv1 / SNMPv2c / SNMPv3
Versions du protocole SNMP. v2c ajoute des types de données enrichis ; v3 apporte authentification, chiffrement et le modèle **USM**.

### sysName / sysUpTime
OID standard de la MIB système : nom d'hôte et durée depuis le dernier démarrage.

### USM (User-based Security Model)
Modèle de sécurité SNMPv3 basé sur des utilisateurs (`createUser`) avec mots de passe d'authentification et de chiffrement distincts.

---

## 4. Zabbix

### Agent 2 (Zabbix Agent 2)
Agent moderne Zabbix (successeur de l'agent 1) supportant plugins, chiffrement PSK/TLS et mode actif/passif.

### Dashboard (Zabbix)
Tableau de bord regroupant widgets (cartes, graphiques, jauges) pour visualiser l'état de l'infrastructure.

### Hôte (Host — Zabbix)
Entité supervisée enregistrée dans Zabbix avec interfaces (Agent, SNMP), templates et macros.

### Item (Zabbix)
Métrique individuelle collectée (ex. charge CPU, requêtes/s Apache). Défini dans un **template**.

### Macro (Zabbix)
Variable configurable par hôte (ex. `{$SNMP_COMMUNITY}`, `{$NGINX.STUB_STATUS.PORT}`) pour personnaliser les templates.

### MariaDB
SGBD relationnel stockant la configuration et l'historique Zabbix (hôtes, items, triggers, événements).

### Mode actif (Zabbix Agent)
L'agent initie la connexion vers le serveur (push des données). Utilisé dans le workshop : le serveur ne contacte jamais l'agent en production.

### Mode passif (Zabbix Agent)
Le serveur interroge l'agent sur le port 10050 (pull). Non utilisé en mode strict du workshop final.

### Network Map (Zabbix)
Schéma visuel des hôtes et de leurs liens, avec code couleur selon l'état (OK / PROBLEM).

### PROBLEM / OK (état Zabbix)
État d'un trigger ou d'un hôte : `PROBLEM` quand une condition d'alerte est remplie, `OK` sinon.

### stub_status (Nginx)
Module Nginx exposant des statistiques internes (connexions actives, requêtes). Surveillé via le template « Nginx by Zabbix agent » sur le port 8081.

### Template (Zabbix)
Modèle réutilisable d'items, triggers et graphiques (ex. `Linux by SNMP`, `Apache by Zabbix agent`).

### Trigger (Zabbix)
Règle d'alerte évaluant les données d'items (ex. « Nginx process is not running »). Passe en PROBLEM si la condition persiste.

### Zabbix Server
Cœur de la plateforme : collecte, corrélation, stockage et notification des événements de supervision.

---

## 5. Observabilité — métriques (Prometheus)

### Alertmanager
Composant Prometheus gérant le routage, le groupement et l'envoi des alertes (email, webhook Slack, etc.) une fois qu'une règle est en état **Firing**.

### Counter (métrique Prometheus)
Métrique monotone croissante (ex. nombre total de requêtes). Le taux s'obtient via `rate()` en **PromQL**.

### Datasource (Grafana)
Connexion configurée dans Grafana vers une source de données (Prometheus, Loki, InfluxDB).

### Exporter
Agent exposant des métriques au format Prometheus. **Node Exporter** exporte les métriques système (CPU, RAM, disque) sur le port 9100.

### Firing / Pending / Inactive
États d'une alerte Prometheus :
- **Inactive** : condition fausse ;
- **Pending** : condition vraie mais délai `for:` non écoulé ;
- **Firing** : alerte active, envoyée à Alertmanager.

### Grafana
Plateforme de visualisation : dashboards, graphiques, alertes. Se connecte à Prometheus, Loki ou InfluxDB via des datasources. Voir aussi [Technologies principales — Grafana](#grafana).

### Histogram (métrique Prometheus)
Métrique mesurant la distribution de valeurs dans des intervalles (**buckets**). Permet de calculer des percentiles via `histogram_quantile()`.

### Instrumentation
Ajout de métriques dans le code applicatif (Flask/FastAPI) via `prometheus_client` : compteurs, histogrammes exposés sur `/metrics`.

### Job (Prometheus)
Groupe logique de cibles dans la configuration Prometheus (ex. `node`, `flask`, `fastapi`).

### Label
Paire clé/valeur attachée à une métrique ou une alerte (ex. `instance`, `status_code`, `severity`). Permet le filtrage en PromQL.

### Node Exporter
Exporter officiel Prometheus pour métriques Linux/Unix (`node_cpu_seconds_total`, `node_memory_MemAvailable_bytes`, etc.).

### Prometheus
Système de monitoring et d'alerting basé sur des séries temporelles. Collecte par **scrape** HTTP périodique des endpoints `/metrics`. Voir aussi [Technologies principales — Prometheus](#prometheus).

### prometheus_client
Bibliothèque Python exposant des métriques Prometheus depuis Flask ou FastAPI.

### PromQL (Prometheus Query Language)
Langage de requête pour interroger et agréger les métriques (`rate()`, `histogram_quantile()`, comparaisons, seuils).

### Pull (modèle de collecte)
Le collecteur (Prometheus) interroge activement les cibles à intervalle fixe (défaut 15 s). Avantage : détection naturelle des pannes (`up == 0`).

### Scrape
Action de Prometheus consistant à récupérer les métriques d'une cible via HTTP GET sur `/metrics`.

### Target (cible Prometheus)
Endpoint surveillé par Prometheus (IP:port). État `up` ou `down` visible dans l'UI ou l'API `/api/v1/targets`.

### Webhook (Alertmanager)
URL appelée par Alertmanager lors d'une alerte. Dans le workshop, déclenche un script d'**auto-healing** sur web-prod.

---

## 6. Observabilité — logs (ELK, Loki)

### Apache Bench (`ab`)
Outil de test de charge HTTP en ligne de commande. Utilisé en séance 5 pour mesurer latences et percentiles sous charge.

### Beats (protocole)
Protocole de communication entre agents légers (Filebeat) et Logstash sur le port 5044.

### Data View (Kibana)
Vue logique sur un ou plusieurs index Elasticsearch, avec champ horodaté `@timestamp` pour l'exploration dans Discover.

### Discover (Kibana)
Interface d'exploration et de recherche de logs en temps réel.

### Elasticsearch (ES)
Moteur de recherche et d'indexation distribué stockant les logs structurés. API REST sur le port 9200.

### ELK Stack
Ensemble **Elasticsearch** + **Logstash** + **Kibana** pour collecter, transformer et visualiser les logs.

### Filebeat
Agent léger lisant des fichiers de log locaux et les envoyant vers Logstash ou Elasticsearch (modèle **push**).

### Grok
Langage de patterns pour parser des lignes de log non structurées en champs (`loglevel`, `client_ip`, `method`, `response_code`). Utilisé dans le pipeline Logstash de la séance 5.

### Index (Elasticsearch)
Collection de documents logiques (ex. `fastapi-logs-2026.03.15`). Kibana interroge les index via un data view.

### Kibana
Interface web d'exploration et de visualisation des données Elasticsearch (Discover, dashboards).

### Logstash
Pipeline ETL de logs : **input** (Beats), **filter** (Grok, mutate), **output** (Elasticsearch).

### Loki
Système d'agrégation de logs inspiré de Prometheus (indexation par labels, pas par contenu complet). Utilisé dans le workshop avec **Promtail**.

### Pipeline (Logstash)
Fichier de configuration décrivant les étapes input → filter → output (`logstash.conf.j2`).

### Promtail
Agent collectant les logs locaux (Nginx access/error) et les poussant vers Loki. Équivalent de Filebeat pour la stack Grafana/Loki.

### Push (modèle de collecte — logs)
L'agent (Filebeat, Promtail) envoie les événements dès qu'ils sont produits, sans attendre une requête du serveur.

### Registre Filebeat
Fichier (`/var/lib/filebeat/registry`) mémorisant la position de lecture dans chaque fichier. Permet la reprise après redémarrage sans perte ni duplication massive.

### Uvicorn
Serveur ASGI haute performance servant l'application FastAPI. Ses logs sont parsés par Grok dans Logstash.

### `_grokparsefailure`
Tag ajouté par Logstash quand une ligne ne correspond pas au pattern Grok défini.

---

## 7. Séries temporelles (InfluxDB)

### Apache Arrow / DataFusion
Moteur analytique columnar sous-jacent à InfluxDB v3. Exécute les requêtes SQL et le **data skipping** via métadonnées Parquet.

### Cardinalité
Nombre de combinaisons uniques de tags ou de séries. Haute cardinalité (millions de valeurs de tags distinctes) posait problème en InfluxDB v1/v2 (index TSI en RAM).

### Data skipping
Optimisation de requête : le moteur élimine les fichiers Parquet dont les métadonnées Min/Max prouvent qu'ils ne contiennent pas les données recherchées (`pruning_predicate` visible dans `EXPLAIN`).

### date_bin
Fonction SQL d'agrégation temporelle dans InfluxDB v3 (équivalent de `TIME_BUCKET`). Regroupe les points par intervalle (ex. 5 minutes).

### Downsampling
Réduction de la résolution temporelle des données anciennes (moyennes horaires stockées dans `usine_historique_5ans`) pour économiser l'espace et accélérer les requêtes long terme.

### EXPLAIN
Commande SQL affichant le plan d'exécution d'une requête (prédicats de pruning, sources hot/cold).

### Hot / Cold (données)
- **Hot** : données récentes dans le **WAL** (écriture rapide) ;
- **Cold** : données historiques compactées en fichiers **Parquet**.

### InfluxDB v3 Core
Version open source d'InfluxDB basée sur le stockage colonnaire Parquet et les requêtes SQL standard. Voir aussi [Technologies principales — InfluxDB](#influxdb).

### Line Protocol (InfluxDB)
Format texte d'écriture des points de mesure : `measurement,tag=value field=value timestamp`. Utilisé via l'API `/api/v3/write_lp`.

### Measurement (InfluxDB)
Équivalent d'une « table » ou série logique (ex. `flux_production`).

### Parquet
Format de fichier columnar compressé. Stockage final des données InfluxDB v3 sur disque.

### Tag / Field (InfluxDB)
- **Tag** : métadonnée indexée (ex. `ligne_id`, `operateur`) — dimension de filtrage ;
- **Field** : valeur mesurée (ex. `temperature`, `vitesse`) — donnée numérique ou textuelle.

### TSI (Time Series Index)
Index inversé des tags en RAM utilisé par InfluxDB v1/v2. Remplacé par le modèle columnar en v3.

### WAL (Write-Ahead Log)
Journal séquentiel des écritures récentes avant flush vers Parquet. Garantit la durabilité et sert de tampon « hot ».

---

## 8. Applications et instrumentation

### ASGI
Interface standard entre serveurs (Uvicorn) et applications Python asynchrones (FastAPI).

### Chaos Engineering
Pratique consistant à provoquer des pannes contrôlées (arrêt service, blocage pare-feu, saturation RAM) pour valider alerting et résilience.

### FastAPI
Framework Python moderne pour APIs REST, utilisé en séance 5 avec middleware Prometheus et logs Uvicorn.

### Flask
Micro-framework Python pour l'API de test de la séance 3, instrumentée avec Counter et Histogram.

### Middleware
Couche interceptant les requêtes HTTP avant/après le traitement. Le middleware FastAPI mesure la durée et incrémente les métriques Prometheus.

### Percentile (p50, p95, p99)
Valeur en dessous de laquelle se situe un pourcentage des mesures. p95 = 95 % des requêtes sont plus rapides que cette valeur.

### stress-ng
Outil générant une charge CPU/RAM/I/O pour tester les alertes (ex. `CPUHigh` en séance 3).

### WSGI / DispatcherMiddleware
Interface entre serveur web et application Flask. `DispatcherMiddleware` monte l'app Prometheus `/metrics` à côté de Flask.

---

## 9. Concepts transversaux

### Auto-healing
Correction automatique d'un incident (ex. redémarrage Nginx via webhook Alertmanager + script `restart-nginx.sh` avec **sudoers** limité).

### Box image / Linked clone
Clone lié VirtualBox partageant le disque de la box parente. `linked_clone = false` est requis sur VirtualBox 7.2 pour éviter l'erreur `E_ACCESSDENIED`.

### DAE (Dossier d'Architecture et d'Exploitation)
Document de synthèse du workshop : architecture, preuves de sécurité, plan de continuité.

### Dashboard (Grafana)
Tableau de bord de métriques et/ou logs (ex. dashboard Node Exporter ID 1860, dashboard unifié M2-Shop).

### Datasource provisioning
Configuration automatique des sources Grafana via fichiers YAML au démarrage (évite la saisie manuelle).

### Endpoint `/metrics`
URL HTTP standard exposant les métriques au format texte Prometheus.

### Infrastructure de supervision / Observabilité
Ensemble des outils permettant de mesurer l'état d'un système :
- **Supervision** : disponibilité, alertes, seuils (SNMP, Zabbix) ;
- **Observabilité** : métriques, logs et traces pour comprendre le comportement interne (Prometheus, ELK, Loki).

### Jalon (workshop)
Étape de validation du projet final : A (réseau), B (métriques sécurisées + Zabbix PSK), C (logs Loki/Grafana), D (alerting + auto-healing).

### M2-Shop
Scénario fictif du workshop : site e-commerce à superviser dans une architecture DMZ sécurisée.

### Métrique
Mesure numérique horodatée (compteur, jauge, histogramme) ou donnée de log structurée.

### Observabilité
Capacité à comprendre l'état interne d'un système à partir de ses sorties (métriques, logs, traces), sans modifier son code pour chaque question.

### Provisioning (Grafana)
Déploiement automatique de datasources, dashboards ou règles d'alerte via fichiers de configuration.

### SRE (Site Reliability Engineering)
Pratiques d'exploitation et de fiabilité des services ; dans le workshop, l'accès Grafana depuis le poste SRE est un flux documenté dans la matrice.

### Sudoers chirurgical
Fichier `/etc/sudoers.d/` autorisant un utilisateur non-root à exécuter **une seule commande précise** (ex. `systemctl restart nginx.service`) pour l'auto-healing sans élévation globale.

### Supervision
Surveillance proactive de l'infrastructure : collecte de données, seuils, alertes et tableaux de bord pour détecter les anomalies.

### Série temporelle
Suite de points de mesure indexés par le temps (timestamp + valeur). Stockée par Prometheus, InfluxDB ou Elasticsearch.

### Token (InfluxDB)
Jeton d'authentification API généré à l'installation (`admin_token.txt`). Remplace login/mot de passe pour les requêtes CLI et curl.

### Variable / group_vars (Ansible)
Fichiers centralisant les paramètres (ports, chemins, secrets vault) partagés entre rôles et playbooks.

---

## Index alphabétique rapide

| Terme | Section |
|-------|---------|
| SNMP | Technologies principales |
| Zabbix | Technologies principales |
| Prometheus | Technologies principales |
| Grafana | Technologies principales |
| InfluxDB | Technologies principales |
| Agent SNMP | SNMP |
| Alertmanager | Prometheus |
| Ansible / Vault | Infrastructure |
| authPriv | SNMP |
| Basic Auth / bcrypt | Réseau |
| Cardinalité | InfluxDB |
| Chaos Engineering | Applications |
| Counter / Histogram | Prometheus |
| Dashboard | Zabbix / Grafana |
| Data skipping | InfluxDB |
| DMZ / Zero-Trust | Réseau |
| Elasticsearch / Kibana / Logstash | Logs |
| Exporter / Node Exporter | Prometheus |
| FastAPI / Flask | Applications |
| Filebeat / Promtail | Logs |
| Grok | Logs |
| Grafana / PromQL | Prometheus |
| InfluxDB / Line Protocol / WAL / Parquet | InfluxDB |
| Infrastructure as Code | Infrastructure |
| Loki | Logs |
| MIB / OID / Trap | SNMP |
| nftables / UFW | Réseau |
| Playbook / Rôle / Handler | Ansible |
| Prometheus / Scrape / Pull | Prometheus |
| PSK / TLS | Réseau |
| SNMPv3 / USM | SNMP |
| systemd / Vagrant / VirtualBox | Infrastructure |
| Template (Zabbix) / Trigger | Zabbix |
| Zabbix Server / Agent 2 | Zabbix |

---

*Glossaire aligné sur le contenu des séances 1 à 6 et du Workshop final (TP Mr Decker).*
