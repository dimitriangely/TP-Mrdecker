# Tests de validation — TP Zabbix 7.0 LTS Supervision Hybride

Ce document recense l'ensemble des tests de validation à exécuter pour certifier que
l'infrastructure est correctement déployée et opérationnelle. Chaque test indique la
commande à exécuter, le résultat attendu et le critère de réussite associé.

---

## 1. Connectivité réseau entre VMs

### 1.1 Ping srv-zabbix → srv-apache

```bash
vagrant ssh srv-zabbix
ping -c 3 192.168.56.11
```

**Résultat attendu :**
```
3 packets transmitted, 3 received, 0% packet loss
```
✅ Critère : 0% packet loss

---

### 1.2 Ping srv-zabbix → srv-nginx

```bash
ping -c 3 192.168.56.12
```

**Résultat attendu :**
```
3 packets transmitted, 3 received, 0% packet loss
```
✅ Critère : 0% packet loss

---

### 1.3 Résolution DNS via /etc/hosts

```bash
ping -c 1 srv-apache
ping -c 1 srv-nginx
```

**Résultat attendu :** résolution correcte des noms vers 192.168.56.11 et 192.168.56.12

✅ Critère : les noms sont résolus sans erreur

---

## 2. MariaDB (srv-zabbix)

### 2.1 Service MariaDB actif

```bash
vagrant ssh srv-zabbix
sudo systemctl is-active mariadb
```

**Résultat attendu :**
```
active
```
✅ Critère : `active`

---

### 2.2 Base zabbix accessible

```bash
sudo mysql -u zabbix -p'Zabbix_TP2024!' zabbix -e "SHOW TABLES;" | wc -l
```

**Résultat attendu :** nombre de lignes > 100 (le schéma Zabbix contient ~170 tables)

✅ Critère : valeur > 100

---

### 2.3 Pas d'erreur de connexion dans le log Zabbix

```bash
sudo grep -i "cannot connect\|error\|failed" /var/log/zabbix/zabbix_server.log | grep -iv "not supported" | tail -20
```

**Résultat attendu :** aucune ligne contenant une erreur de connexion à la base

✅ Critère : sortie vide ou uniquement des messages "not supported" (items non critiques)

---

## 3. Zabbix Server (srv-zabbix)

### 3.1 Service zabbix-server actif

```bash
vagrant ssh srv-zabbix
sudo systemctl is-active zabbix-server
```

**Résultat attendu :**
```
active
```
✅ Critère : `active`

---

### 3.2 Port 10051 en écoute

```bash
sudo ss -tlnp | grep 10051
```

**Résultat attendu :**
```
LISTEN  0  ...  0.0.0.0:10051  ...  zabbix_server
```
✅ Critère : port 10051 en écoute

---

### 3.3 Zabbix server confirmé en cours d'exécution dans le log

```bash
sudo grep "Zabbix Server started" /var/log/zabbix/zabbix_server.log | tail -3
```

**Résultat attendu :** au moins une ligne avec `Zabbix Server started`

✅ Critère : ligne présente

---

### 3.4 Interface web accessible

Depuis le navigateur hôte :
```
http://localhost:8080/zabbix
```

**Résultat attendu :** page de login Zabbix 7.0

✅ Critère : connexion avec `Admin` / `zabbix` réussie

---

## 4. SNMP (srv-apache et srv-nginx)

### 4.1 Service snmpd actif sur srv-apache

```bash
vagrant ssh srv-apache
sudo systemctl is-active snmpd
```

**Résultat attendu :**
```
active
```
✅ Critère : `active`

---

### 4.2 snmpd écoute sur toutes les interfaces (srv-apache)

```bash
sudo ss -ulnp | grep 161
```

**Résultat attendu :**
```
UNCONN  0  0  0.0.0.0:161  0.0.0.0:*  snmpd
```
✅ Critère : écoute sur `0.0.0.0:161` (pas seulement `127.0.0.1`)

---

### 4.3 snmpwalk local sur srv-apache

```bash
snmpwalk -v2c -c tp_admin 127.0.0.1 system.sysDescr.0
```

**Résultat attendu :**
```
SNMPv2-MIB::sysDescr.0 = STRING: Linux srv-apache ...
```
✅ Critère : description système retournée

---

### 4.4 snmpwalk depuis srv-zabbix vers srv-apache

```bash
vagrant ssh srv-zabbix
snmpwalk -v2c -c tp_admin 192.168.56.11 system.sysDescr.0
```

**Résultat attendu :**
```
SNMPv2-MIB::sysDescr.0 = STRING: Linux srv-apache ...
```
✅ Critère : description système retournée depuis le réseau

---

### 4.5 snmpwalk depuis srv-zabbix vers srv-nginx

```bash
snmpwalk -v2c -c tp_admin 192.168.56.12 system.sysDescr.0
```

**Résultat attendu :**
```
SNMPv2-MIB::sysDescr.0 = STRING: Linux srv-nginx ...
```
✅ Critère : description système retournée depuis le réseau

---

### 4.6 Communauté incorrecte refusée

```bash
snmpwalk -v2c -c mauvaise_communaute 192.168.56.11 system.sysDescr.0
```

**Résultat attendu :**
```
Timeout: No Response from 192.168.56.11
```
✅ Critère : timeout (pas de réponse avec une communauté incorrecte)

---

## 5. Apache2 + mod_status (srv-apache)

### 5.1 Service Apache2 actif

```bash
vagrant ssh srv-apache
sudo systemctl is-active apache2
```

**Résultat attendu :**
```
active
```
✅ Critère : `active`

---

### 5.2 mod_status accessible en local

```bash
curl -s http://localhost/server-status?auto | head -5
```

**Résultat attendu :**
```
localhost
ServerVersion: Apache/2.x.x
...
Total Accesses: ...
```
✅ Critère : `Total Accesses` présent dans la sortie

---

### 5.3 mod_status inaccessible depuis l'extérieur

```bash
# Depuis srv-zabbix
curl -s http://192.168.56.11/server-status
```

**Résultat attendu :** code 403 Forbidden ou connexion refusée

✅ Critère : accès refusé depuis le réseau

---

## 6. Nginx + stub_status (srv-nginx)

### 6.1 Service Nginx actif

```bash
vagrant ssh srv-nginx
sudo systemctl is-active nginx
```

**Résultat attendu :**
```
active
```
✅ Critère : `active`

---

### 6.2 stub_status accessible en local (port 8081)

```bash
curl -s http://127.0.0.1:8081/nginx_status
```

**Résultat attendu :**
```
Active connections: 1
server accepts handled requests
 ...
Reading: 0 Writing: 1 Waiting: 0
```
✅ Critère : `Active connections` présent dans la sortie

---

### 6.3 stub_status inaccessible depuis l'extérieur

```bash
# Depuis srv-zabbix
curl -s http://192.168.56.12:8081/nginx_status
```

**Résultat attendu :** connexion refusée (port non exposé sur 0.0.0.0)

✅ Critère : accès refusé depuis le réseau

---

## 7. Zabbix Agent 2 (srv-apache et srv-nginx)

### 7.1 Service zabbix-agent2 actif sur srv-apache

```bash
vagrant ssh srv-apache
sudo systemctl is-active zabbix-agent2
```

**Résultat attendu :**
```
active
```
✅ Critère : `active`

---

### 7.2 Port 10050 en écoute sur srv-apache

```bash
sudo ss -tlnp | grep 10050
```

**Résultat attendu :**
```
LISTEN  0  ...  0.0.0.0:10050  ...  zabbix_agent2
```
✅ Critère : port 10050 en écoute

---

### 7.3 Configuration agent pointant vers srv-zabbix

```bash
grep "^Server=" /etc/zabbix/zabbix_agent2.conf
```

**Résultat attendu :**
```
Server=192.168.56.10
```
✅ Critère : IP du serveur Zabbix correcte

---

### 7.4 Même tests sur srv-nginx

```bash
vagrant ssh srv-nginx
sudo systemctl is-active zabbix-agent2
sudo ss -tlnp | grep 10050
grep "^Server=" /etc/zabbix/zabbix_agent2.conf
```

✅ Critère : `active`, port 10050 ouvert, Server=192.168.56.10

---

## 8. Interface Zabbix — Hôtes

### 8.1 Icônes ZBX et SNMP au vert

Dans l'UI Zabbix : **Data collection → Hosts**

| Hôte           | ZBX    | SNMP   |
|----------------|--------|--------|
| srv-apache     | ✅ vert | ✅ vert |
| srv-nginx      | ✅ vert | ✅ vert |
| Zabbix server  | ✅ vert | —      |

✅ Critère : toutes les icônes vertes

---

### 8.2 Nombre d'items collectés

Dans **Data collection → Hosts**, vérifier que le nombre d'items est > 0 pour chaque hôte.

| Hôte           | Items attendus (ordre de grandeur) |
|----------------|------------------------------------|
| srv-apache     | > 80                               |
| srv-nginx      | > 60                               |
| Zabbix server  | > 100                              |

✅ Critère : items > 0 et en cours de collecte

---

## 9. Network Map

### 9.1 Carte Infrastructure TP

Dans **Monitoring → Maps → Infrastructure TP** :

- Les 3 nœuds (SRV-ZABBIX, SRV-APACHE, SRV-NGINX) sont affichés
- Les liens réseau sont verts
- Chaque nœud affiche `OK` en dessous

✅ Critère : 3 nœuds OK, liens verts

---

## 10. Dashboards

### 10.1 Dashboard "Vue Générale"

| Widget              | Vérification                              |
|---------------------|-------------------------------------------|
| Map                 | 3 nœuds verts visibles                    |
| Trafic réseau sortant | Graphique avec axes temporels           |
| CPU Zabbix Server   | Gauge affichant une valeur entre 0 et 100 |

✅ Critère : les 3 widgets affichent des données

---

### 10.2 Dashboard "Web Performance"

| Widget               | Vérification                              |
|----------------------|-------------------------------------------|
| Requêtes par seconde | 2 lignes (srv-apache + srv-nginx) avec valeurs |
| Alertes services Web | Vide si tout est OK, alertes si problème  |

✅ Critère : tableau avec 2 hôtes et valeurs de requêtes/sec

---

## 11. Test d'alerte — Arrêt de Nginx

### 11.1 Procédure

```bash
# 1. Arrêter Nginx sur srv-nginx
vagrant ssh srv-nginx
sudo systemctl stop nginx

# 2. Attendre 60 à 120 secondes

# 3. Vérifier le trigger dans Zabbix
# Data collection → Hosts → srv-nginx → Triggers
# Chercher : "Nginx process discovery: Nginx: Process is not running"
```

**Résultat attendu :** trigger en PROBLEM (rouge)

✅ Critère : trigger PROBLEM détecté

---

### 11.2 Rétablissement du service

```bash
sudo systemctl start nginx
```

**Résultat attendu :** trigger repassé en OK dans les 60 secondes suivantes

✅ Critère : trigger OK après redémarrage

---

## 12. Récapitulatif des critères de réussite de l'énoncé

| Critère officiel                                                              | Statut |
|-------------------------------------------------------------------------------|--------|
| Indicateurs SNMP et Agent au vert (icônes dans la liste des hôtes)           | ✅     |
| Pas d'erreurs de connexion DB dans `/var/log/zabbix/zabbix_server.log`       | ✅     |
| Arrêt manuel de Nginx → alerte critique dans les 60 secondes                 | ✅     |
| Graphiques affichant des données historiques (CPU, RAM, Trafic)               | ✅     |

---

## Annexe — Commandes de diagnostic rapide

```bash
# État global de tous les services sur srv-zabbix
vagrant ssh srv-zabbix -c "sudo systemctl is-active mariadb zabbix-server apache2 zabbix-agent"

# État global sur srv-apache
vagrant ssh srv-apache -c "sudo systemctl is-active snmpd apache2 zabbix-agent2"

# État global sur srv-nginx
vagrant ssh srv-nginx -c "sudo systemctl is-active snmpd nginx zabbix-agent2"

# Dernières lignes du log Zabbix
vagrant ssh srv-zabbix -c "sudo tail -20 /var/log/zabbix/zabbix_server.log"

# Test SNMP complet depuis srv-zabbix
vagrant ssh srv-zabbix -c "snmpwalk -v2c -c tp_admin 192.168.56.11 system && snmpwalk -v2c -c tp_admin 192.168.56.12 system"
```