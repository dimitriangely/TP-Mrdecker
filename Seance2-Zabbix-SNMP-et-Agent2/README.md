# TP Zabbix 7.0 LTS — Supervision Hybride SNMP + Agent

## Architecture

| VM           | IP             | Rôle           | Services                              |
|--------------|----------------|----------------|---------------------------------------|
| srv-zabbix   | 192.168.56.10  | Serveur maître | MariaDB, Zabbix Server, Apache2, PHP  |
| srv-apache   | 192.168.56.11  | Web 1          | Apache2, SNMPd, Zabbix Agent 2        |
| srv-nginx    | 192.168.56.12  | Web 2          | Nginx, SNMPd, Zabbix Agent 2          |

---

## Prérequis

- VirtualBox installé (version 7.x)
- Vagrant installé
- `linked_clone = false` dans le Vagrantfile (requis sur VirtualBox 7.2 — évite l'erreur E_ACCESSDENIED)

---

## Lancement

```bash
# Démarrage VM par VM (recommandé)
vagrant up srv-zabbix
vagrant up srv-apache
vagrant up srv-nginx

# Ou tout d'un coup
vagrant up
```

### Autres commandes utiles

```bash
vagrant ssh srv-zabbix
vagrant provision srv-apache   # reprovisionner sans redémarrer
vagrant destroy -f && vagrant up  # reset complet
```

---

## Problèmes connus et solutions

### 1. Box Debian 13 indisponible
`debian/trixie64` n'est pas encore stable sur Vagrant Cloud. Ce TP utilise `debian/bookworm64` (Debian 12), entièrement supportée par Zabbix 7.0. Pour basculer sur Trixie quand disponible : modifier `box` dans le Vagrantfile et `zabbix_debian_codename` dans `ansible/roles/zabbix_server/defaults/main.yml`.

### 2. Erreur VirtualBox E_ACCESSDENIED (linked clone)
Si `vagrant up` échoue avec `VBoxManage showvminfo E_ACCESSDENIED`, passer `linked_clone` à `false` dans le Vagrantfile pour les 3 VMs.

### 3. snmpd écoute uniquement sur 127.0.0.1
Le template Ansible déploie `agentaddress udp:0.0.0.0:161`. Si snmpd refuse de répondre depuis le réseau, corriger manuellement :
```bash
sudo sed -i 's/^agentaddress.*/agentaddress udp:0.0.0.0:161/' /etc/snmp/snmpd.conf
sudo systemctl restart snmpd
```

### 4. snmp-mibs-downloader introuvable
Le paquet est dans le dépôt `non-free`. Le rôle `common` active automatiquement `non-free non-free-firmware` dans `/etc/apt/sources.list`.

### 5. Interface web Zabbix — page Apache par défaut
Accéder via `http://localhost:8080/zabbix` (et non `http://localhost:8080`).

### 6. Warning locale en_US lors du wizard Zabbix
Non bloquant. Pour le corriger :
```bash
sudo dpkg-reconfigure locales  # sélectionner en_US.UTF-8
sudo systemctl restart apache2
```

### 7. Nginx stub_status — port 8081
Le template Zabbix "Nginx by Zabbix agent" cherche par défaut sur le port 80. Notre configuration utilise le port 8081 pour éviter le conflit avec le vhost par défaut. Ajouter ces macros sur l'hôte srv-nginx dans l'UI Zabbix :
- `{$NGINX.STUB_STATUS.PATH}` = `nginx_status`
- `{$NGINX.STUB_STATUS.PORT}` = `8081`

### 8. Triggers Nginx désactivés par défaut
Les triggers "Nginx process discovery" sont désactivés par défaut dans le template. Les activer manuellement dans Data collection → Hosts → srv-nginx → Triggers.

---

## Accès à l'interface web Zabbix

```
http://localhost:8080/zabbix
```

Identifiants par défaut : `Admin` / `zabbix`

---

## Configuration UI Zabbix (Partie 5 — manuelle)

### 1. Ajouter les hôtes (Data collection → Hosts → Create host)

**SRV-APACHE** :
- Hostname : `srv-apache`
- Templates : `Linux by SNMP` + `Apache by Zabbix agent`
- Host groups : `Linux servers`
- Interface Agent : `192.168.56.11:10050`
- Interface SNMP : `192.168.56.11:161`, SNMPv2, `{$SNMP_COMMUNITY}`
- Macro : `{$SNMP_COMMUNITY}` = `tp_admin`

**SRV-NGINX** :
- Hostname : `srv-nginx`
- Templates : `Linux by SNMP` + `Nginx by Zabbix agent`
- Host groups : `Linux servers`
- Interface Agent : `192.168.56.12:10050`
- Interface SNMP : `192.168.56.12:161`, SNMPv2, `{$SNMP_COMMUNITY}`
- Macros :
  - `{$SNMP_COMMUNITY}` = `tp_admin`
  - `{$NGINX.STUB_STATUS.PATH}` = `nginx_status`
  - `{$NGINX.STUB_STATUS.PORT}` = `8081`

### 2. Activer les triggers Nginx

Data collection → Hosts → srv-nginx → Triggers → activer :
- `Nginx process discovery: Nginx: Process is not running`
- `Nginx process discovery: Nginx: Service is down`

### 3. Network Map (Monitoring → Maps → Create map)

- Name : `Infrastructure TP`, Width : 800, Height : 600
- Ajouter 3 éléments Host : Zabbix server, srv-apache, srv-nginx
- Relier avec des liens (Ctrl+clic sur 2 nœuds → Link: Add)

### 4. Dashboard "Vue Générale"

| Widget | Type  | Configuration                                      |
|--------|-------|----------------------------------------------------|
| Map    | Map   | Infrastructure TP                                  |
| Graph  | Graph | srv-apache + srv-nginx, items outgoing/sent        |
| Gauge  | Gauge | Zabbix server → CPU utilization, min 0 max 100     |

### 5. Dashboard "Web Performance"

| Widget              | Type      | Configuration                              |
|---------------------|-----------|--------------------------------------------|
| Requêtes par seconde | Top hosts | Linux servers, colonne "Requests per second" |
| Alertes services Web | Problems  | Linux servers                              |

---

## Test de déclenchement d'alerte (critère de réussite)

```bash
# Arrêter Nginx sur srv-nginx
vagrant ssh srv-nginx -c "sudo systemctl stop nginx"

# Observer le trigger passer en PROBLEM dans :
# Data collection → Hosts → srv-nginx → Triggers
# "Nginx process discovery: Nginx: Process is not running" → PROBLEM ✅

# Redémarrer Nginx
vagrant ssh srv-nginx -c "sudo systemctl start nginx"
```

---

## Critères de réussite validés

- [x] Indicateurs SNMP et Agent au vert sur les 3 hôtes
- [x] Pas d'erreurs de connexion DB dans `/var/log/zabbix/zabbix_server.log`
- [x] Arrêt Nginx → trigger PROBLEM détecté
- [x] Graphiques avec données historiques (CPU, requêtes/sec)

---

## Notes techniques

| Paramètre              | Valeur                |
|------------------------|-----------------------|
| Mot de passe MariaDB   | `Zabbix_TP2024!`      |
| Communauté SNMP        | `tp_admin`            |
| Port Zabbix Agent      | `10050`               |
| Port SNMP              | `161`                 |
| Port stub_status Nginx | `8081`                |
| Port interface web     | `8080` (hôte → 80 VM) |