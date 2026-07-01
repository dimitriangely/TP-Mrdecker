# Tests de Validation — TP Observabilité Sécurisée

 Ce fichier répertorie toutes les commandes permettant de rejouer
 les tests de validation des Jalons A, B, C et D avant toute remise
 en service après incident ou reconstruction de l'infrastructure.
#
 Convention d'exécution : toutes les commandes sont lancées depuis
 l'hôte Windows via PowerShell (vagrant ssh ...) ou depuis les VMs
 elles-mêmes. Aucune commande n'est exécutée depuis l'hôte Ansible.
#
# Statut attendu de chaque test : ✅ = résultat conforme
#                                  ❌ = anomalie à investiguer

---

## Prérequis

```powershell
# Vérifier que les 3 VMs sont up avant de commencer
vagrant status
```

**Résultat attendu :**
```
web-prod   running (virtualbox)
fw-router  running (virtualbox)
supervision running (virtualbox)
```

---

## JALON A — Cloisonnement et Filtrage Réseau (Zero-Trust)

### A.1 — Vérification des routes statiques inter-zones

```powershell
vagrant ssh web-prod -c "ip route show 10.0.10.0/24"
vagrant ssh supervision -c "ip route show 10.0.20.0/24"
```

**Résultat attendu :**
```
# web-prod :
10.0.10.0/24 via 10.0.20.1 dev eth1

# supervision :
10.0.20.0/24 via 10.0.10.1 dev eth1
```

> Sans ces routes, les paquets inter-zones partent vers la passerelle NAT
> VirtualBox et le Zero-Trust devient inopérant (timeouts silencieux).

---

### A.2 — Test Zero-Trust : port non autorisé doit TIMEOUT

```powershell
vagrant ssh web-prod -c "timeout 5 nc -zv 10.0.10.5 22 || echo 'TIMEOUT OK - Zero-Trust valide'"
```

**Résultat attendu :**
```
TIMEOUT OK - Zero-Trust valide
```

> Le port 22 de supervision n'est pas dans la matrice de flux autorisés.
> Le fw-router droppe silencieusement → timeout côté client.

---

### A.3 — Test Zero-Trust : port autorisé doit TRAVERSER le routeur

```powershell
vagrant ssh web-prod -c "nc -zv -w 3 10.0.10.5 10051"
```

**Résultat attendu :**
```
supervision [10.0.10.5] 10051 (zabbix-trapper) : Connection refused
```

> "Connection refused" (RST) et non "timeout" : le paquet a bien traversé
> fw-router, atteint supervision, et a été rejeté faute de service en écoute
> sur ce port précis à ce moment. C'est la preuve que le FORWARD est actif.

---

### A.4 — Vérification des règles nftables sur fw-router

```powershell
vagrant ssh fw-router -c "sudo nft list ruleset"
```

**Résultat attendu (extrait chaîne forward) :**
```
chain forward {
    type filter hook forward priority filter; policy drop;
    ct state established,related accept
    iifname "eth2" oifname "eth1" ip saddr 10.0.10.5 ip daddr 10.0.20.20 tcp dport 9100 ...accept
    iifname "eth1" oifname "eth2" ip saddr 10.0.20.20 ip daddr 10.0.10.5 tcp dport 10051 ...accept
    iifname "eth1" oifname "eth2" ip saddr 10.0.20.20 ip daddr 10.0.10.5 tcp dport 3100 ...accept
    iifname "eth2" oifname "eth1" ip saddr 10.0.10.5 ip daddr 10.0.20.20 tcp dport 9095 ...accept
    log prefix "NFT-FORWARD-DROP: " counter drop
}
```

> Policy drop par défaut, 4 règles FORWARD explicites (9100, 10051, 3100, 9095),
> log sur tout le reste. Toute règle manquante = anomalie.

---

### A.5 — Vérification des règles nftables sur web-prod

```powershell
vagrant ssh web-prod -c "sudo nft list ruleset | grep -E 'policy|accept|drop'"
```

**Résultat attendu :**
```
type filter hook input priority filter; policy drop;
... accept  (lo, established, 443, 80, 9100 depuis 10.0.10.5, 9095 depuis 10.0.10.5, 22)
log prefix "NFT-WEBPROD-INPUT-DROP: " counter drop
type filter hook output priority filter; policy drop;
... accept  (lo, established, 10051 vers 10.0.10.5, 3100 vers 10.0.10.5, 443, 80, 53)
log prefix "NFT-WEBPROD-OUTPUT-DROP: " counter drop
type filter hook forward priority filter; policy drop;
```

---

## JALON B — Durcissement et Chiffrement des Collecteurs

### B.1 — Node Exporter : écoute active sur le port 9100

```powershell
vagrant ssh web-prod -c "sudo ss -tpln | grep 9100"
```

**Résultat attendu :**
```
LISTEN  0  4096  *:9100  *:*  users:(("node_exporter",...))
```

---

### B.2 — Node Exporter : accès sans credentials → 401 Unauthorized

```powershell
vagrant ssh web-prod -c "curl -k -s -o /dev/null -w '%{http_code}\n' https://localhost:9100/metrics"
```

**Résultat attendu :**
```
401
```

> C'est le test explicitement listé dans le protocole de recette du sujet.
> Tout autre code (200, 000, 403) indique un problème de configuration.

---

### B.3 — Node Exporter : TLS v1.3 forcé

```powershell
vagrant ssh web-prod -c "echo | openssl s_client -connect localhost:9100 -tls1_3 2>&1 | grep -E 'Protocol|Cipher'"
```

**Résultat attendu :**
```
New, TLSv1.3, Cipher is TLS_AES_128_GCM_SHA256
    Protocol  : TLSv1.3
    Cipher    : TLS_AES_128_GCM_SHA256
```

---

### B.4 — Prometheus : target web-prod en état "up"

```powershell
vagrant ssh supervision -c "curl -s 'http://localhost:9090/api/v1/targets' | python3 -m json.tool | grep -E 'health|lastError|instance'"
```

**Résultat attendu :**
```json
"health": "up",
"instance": "10.0.20.20:9100",
"lastError": "",
```

> "health": "up" + "lastError": "" confirment que le scraping HTTPS
> avec Basic Auth et insecure_skip_verify fonctionne de bout en bout
> à travers fw-router.

---

### B.5 — Zabbix Agent2 : service actif et hostname correct

```powershell
vagrant ssh web-prod -c "sudo systemctl is-active zabbix-agent2"
vagrant ssh web-prod -c "sudo grep -E '^(Hostname|ServerActive|TLSConnect)' /etc/zabbix/zabbix_agent2.conf"
```

**Résultat attendu :**
```
active

Hostname=web-prod
ServerActive=10.0.10.5
TLSConnect=psk
```

---

### B.6 — Zabbix Server : service actif

```powershell
vagrant ssh supervision -c "sudo systemctl is-active zabbix-server"
```

**Résultat attendu :**
```
active
```

---

### B.7 — Zabbix PSK : hôte web-prod enregistré avec les bons paramètres

```powershell
vagrant ssh supervision
# Puis, depuis le shell Linux :
sudo mysql -uzabbix -p'fSLNscRLY6T07YjOMvosPZpf' zabbix \
  -e "SELECT hostid, host, tls_connect, tls_accept, tls_psk_identity FROM hosts WHERE host='web-prod';"
exit
```

**Résultat attendu :**
```
+--------+----------+-------------+------------+-----------------+
| hostid | host     | tls_connect | tls_accept | tls_psk_identity|
+--------+----------+-------------+------------+-----------------+
|  10683 | web-prod |           2 |          2 | PSK_WEBPROD_001 |
+--------+----------+-------------+------------+-----------------+
```

> tls_connect=2 et tls_accept=2 signifient "PSK uniquement".
> hostid ≠ 0 est impératif (0 = ligne invalide ignorée par Zabbix Server).

---

### B.8 — Zabbix PSK : aucune erreur de handshake dans les logs

```powershell
vagrant ssh supervision -c "sudo tail -20 /var/log/zabbix/zabbix_server.log | grep -iE 'error|PSK|handshake'"
vagrant ssh web-prod -c "sudo tail -20 /var/log/zabbix/zabbix_agent2.log | grep -iE 'error|fail|refused'"
```

**Résultat attendu :**
```
# Aucune ligne de log contenant error/PSK/handshake/fail/refused
# (absence = bon signe — Zabbix ne logue que les erreurs et les changements d'état)
```

> Si des erreurs "no suitable signature algorithm" apparaissent →
> mettre à jour openssl/libssl3 et redémarrer les deux services Zabbix.

---

## JALON C — Centralisation des Logs et Dashboarding

### C.1 — Nginx : disponible en HTTPS, réponse 200

```powershell
vagrant ssh web-prod -c "curl -k -s -o /dev/null -w '%{http_code}\n' https://localhost/"
```

**Résultat attendu :**
```
200
```

---

### C.2 — Nginx : logs access.log et error.log présents

```powershell
vagrant ssh web-prod -c "sudo ls -la /var/log/nginx/"
```

**Résultat attendu :**
```
-rw-r-----  1 www-data adm  ...  access.log
-rw-r-----  1 www-data adm  ...  error.log
```

---

### C.3 — Promtail : service actif et targets ready

```powershell
vagrant ssh web-prod -c "sudo systemctl is-active promtail"
vagrant ssh web-prod -c "curl -s http://localhost:9080/targets | grep -o 'ready.*true' | head -5"
```

**Résultat attendu :**
```
active

# Deux occurrences de "ready":
# true (nginx_access 1/1 ready)
# true (nginx_error 1/1 ready)
```

---

### C.4 — Loki : réception confirmée des labels Nginx

```powershell
vagrant ssh supervision -c "curl -s 'http://localhost:3100/loki/api/v1/label/job/values'"
```

**Résultat attendu :**
```json
{"status":"success","data":["nginx_access","nginx_error"]}
```

> Si data est vide, vérifier que Promtail a bien envoyé des logs
> (générer du trafic Nginx : curl -k https://10.0.20.20/ depuis supervision).

---

### C.5 — Grafana : service actif en HTTPS

```powershell
vagrant ssh supervision -c "sudo systemctl is-active grafana"
vagrant ssh supervision -c "curl -k -s -o /dev/null -w '%{http_code}\n' https://localhost:3000/api/health"
```

**Résultat attendu :**
```
active
200
```

---

### C.6 — Grafana : datasources provisionnées automatiquement

```powershell
vagrant ssh supervision -c "curl -k -s -u admin:admin 'https://localhost:3000/api/datasources' | python3 -m json.tool | grep -E 'name|type|uid'"
```

**Résultat attendu :**
```json
"name": "Prometheus",
"type": "prometheus",
"uid": "prometheus_ds",
...
"name": "Loki",
"type": "loki",
"uid": "loki_ds",
```

---

### C.7 — Grafana : dashboard unifié M2-Shop présent

```powershell
vagrant ssh supervision -c "curl -k -s -u admin:admin 'https://localhost:3000/api/search?query=M2-Shop' | python3 -m json.tool | grep -E 'title|uid|folderTitle'"
```

**Résultat attendu :**
```json
"title": "M2-Shop - Observabilité Unifiée (Production)",
"uid": "m2shop-unified-prod",
"folderTitle": "M2-Shop",
```

---

## JALON D — Alerting et Remédiation Automatique

### D.1 — Alertmanager : service actif

```powershell
vagrant ssh supervision -c "sudo systemctl is-active alertmanager"
```

**Résultat attendu :**
```
active
```

---

### D.2 — Prometheus : métrique systemd Nginx exposée

```powershell
vagrant ssh supervision -c "curl -s 'http://localhost:9090/api/v1/query?query=node_systemd_unit_state%7Bname%3D%22nginx.service%22%2Cstate%3D%22active%22%7D' | python3 -m json.tool | grep value"
```

**Résultat attendu :**
```json
"value": [..., "1"]
```

> Valeur 1 = nginx.service est actif.
> Valeur 0 = nginx.service est arrêté → l'alerte NginxDown doit se déclencher.

---

### D.3 — Webhook receiver : service actif

```powershell
vagrant ssh web-prod -c "sudo systemctl is-active webhook-receiver"
```

**Résultat attendu :**
```
active
```

---

### D.4 — Sudoers chirurgical : vérification des droits du compte healer

```powershell
vagrant ssh web-prod -c "sudo -u healer sudo -n -l"
```

**Résultat attendu :**
```
User healer may run the following commands on web-prod:
    (root) NOPASSWD: /usr/bin/systemctl restart nginx.service
```

> Une seule commande exacte autorisée, aucun wildcard, aucune autre commande.
> Si plus d'une commande apparaît → anomalie de configuration sudoers.

---

### D.5 — CRASH TEST COMPLET (protocole de recette du sujet)

> ⚠ Ce test coupe temporairement le service web public M2-Shop.
> Ne l'exécuter qu'en contexte de validation contrôlée.

```powershell
# Étape 1 — Couper Nginx (simule la panne)
vagrant ssh web-prod -c "sudo systemctl stop nginx"

# Étape 2 — Attendre 15 secondes (le cycle de scraping Prometheus est à 10s)
Start-Sleep -Seconds 15

# Étape 3 — Vérifier que Nginx a été relancé automatiquement
vagrant ssh web-prod -c "sudo systemctl is-active nginx"
```

**Résultat attendu (étape 3) :**
```
active
```

---

### D.6 — Vérification des logs d'auto-healing

```powershell
vagrant ssh web-prod -c "sudo cat /var/log/healer/remediation.log"
vagrant ssh web-prod -c "sudo cat /var/log/healer/webhook-receiver.log | tail -10"
```

**Résultat attendu :**
```
# remediation.log :
[2026-06-30T19:25:34Z] Déclenchement de la remédiation automatique : relance de nginx.service
[2026-06-30T19:25:34Z] Remédiation réussie : nginx.service relancé

# webhook-receiver.log :
... INFO Alerte NginxDown (firing) reçue - déclenchement du script de remédiation
... INFO Script exécuté, code retour=0, stdout=, stderr=
... INFO HTTP "POST /alert HTTP/1.1" 204 -
```

> code retour=0 = succès. Un code retour non nul indique que systemctl
> n'a pas pu relancer Nginx → vérifier les logs du service.

---

### D.7 — Vérification de l'alerte dans Alertmanager

```powershell
vagrant ssh supervision -c "curl -s http://localhost:9093/api/v2/alerts | python3 -m json.tool | grep -E 'alertname|status|startsAt'"
```

**Résultat attendu (pendant la panne) :**
```json
"alertname": "NginxDown",
"state": "active",
"startsAt": "...",
```

**Résultat attendu (après rétablissement) :**
```
[] (tableau vide — plus aucune alerte active)
```

---

### D.8 — Vérification du délai de remédiation (< 60 secondes)

```powershell
# Comparer les timestamps dans remediation.log et webhook-receiver.log
vagrant ssh web-prod -c "sudo grep -E 'Déclenchement|réussie' /var/log/healer/remediation.log | tail -2"
```

**Résultat attendu :**
```
[2026-06-30T19:25:34Z] Déclenchement de la remédiation automatique : relance de nginx.service
[2026-06-30T19:25:34Z] Remédiation réussie : nginx.service relancé
```

> Même seconde entre déclenchement et succès = délai < 1 seconde
> (exigence du sujet : < 60 secondes — largement respecté).

---

## Récapitulatif des tests

| Jalon | Test | Commande principale | Résultat attendu |
|-------|------|---------------------|-----------------|
| A | Route statique inter-zones | `ip route show 10.0.10.0/24` | via 10.0.20.1 dev eth1 |
| A | Port non autorisé | `nc -zv 10.0.10.5 22` | TIMEOUT |
| A | Port autorisé traverse le routeur | `nc -zv -w 3 10.0.10.5 10051` | Connection refused |
| A | Règles nftables fw-router | `nft list ruleset` | policy drop + 4 règles FORWARD |
| B | Node Exporter : 401 sans auth | `curl -k .../metrics` | **401** |
| B | Node Exporter : TLS v1.3 | `openssl s_client -tls1_3` | TLSv1.3 + AES_128_GCM |
| B | Prometheus target | `/api/v1/targets` | health=up, lastError="" |
| B | Zabbix PSK hostid valide | `SELECT hostid FROM hosts` | hostid ≠ 0, tls_connect=2 |
| C | Nginx HTTPS | `curl -k -w '%{http_code}'` | **200** |
| C | Promtail targets | `/targets` | 1/1 ready (access + error) |
| C | Loki labels | `/loki/api/v1/label/job/values` | nginx_access, nginx_error |
| C | Grafana health | `/api/health` | **200** (HTTPS) |
| C | Grafana datasources | `/api/datasources` | prometheus_ds, loki_ds |
| D | Sudoers healer | `sudo -u healer sudo -n -l` | 1 commande exacte uniquement |
| D | Crash Test | `systemctl stop nginx` → attente 15s | nginx = active |
| D | Logs auto-healing | `cat remediation.log` | code retour=0, réussie |
| D | Délai de remédiation | timestamps remediation.log | < 60 secondes |
