# TP Observabilité Avancée — FastAPI, Prometheus, ELK

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  Machine hôte Windows                                                 │
│  localhost:5000 → FastAPI          localhost:9090 → Prometheus        │
│  localhost:3000 → Grafana          localhost:9200 → Elasticsearch     │
│  localhost:5601 → Kibana                                              │
└───────────┬──────────────────────────────┬───────────────────────────┘
            │                              │
   ┌────────┴──────────┐         ┌─────────┴──────────────┐
   │  VM 1 — cible     │         │  VM 2 — monitoring     │
   │  192.168.56.10    │         │  192.168.56.20          │
   │                   │─pull────▶  Prometheus    :9090   │
   │  • FastAPI  :5000 │─push────▶  Logstash      :5044   │
   │  • Node Exp :9100 │         │  Elasticsearch :9200   │
   │  • Filebeat       │         │  Kibana        :5601   │
   │  • UFW (pare-feu) │         │  Grafana       :3000   │
   └───────────────────┘         └────────────────────────┘
```

**Deux modèles de collecte :**
- **Pull** : Prometheus va chercher les métriques toutes les 15s (FastAPI, Node Exporter)
- **Push** : Filebeat envoie les logs vers Logstash en continu

---

## Prérequis

- VirtualBox ≥ 6.1 / Vagrant ≥ 2.3
- **VM 2 nécessite 4 Go de RAM** (ELK est gourmand)
- Connexion Internet lors du provisioning

---

## Démarrage

```powershell
cd Seance5-Prometheus-suite

# Démarrer les deux VMs
vagrant up

# Accès aux interfaces
# FastAPI      : http://localhost:5000
# Prometheus   : http://localhost:9090
# Grafana      : http://localhost:3000  (admin / admin123)
# Kibana       : http://localhost:5601
# Elasticsearch: http://localhost:9200
```

---

## Vérifications manuelles

```bash
# VM 1 — cible
vagrant ssh cible
systemctl status api-fastapi
systemctl status node_exporter
systemctl status filebeat
sudo ufw status verbose
curl http://localhost:5000/health
curl http://localhost:5000/metrics | grep api_requests

# VM 2 — monitoring
vagrant ssh monitoring
systemctl status elasticsearch
systemctl status logstash
systemctl status kibana
curl http://localhost:9200
curl http://localhost:9090/api/v1/targets | python3 -m json.tool
```

---

## Générer du trafic sur l'API

```powershell
# Depuis PowerShell Windows — 100 requêtes espacées de 200ms
for ($i=0; $i -lt 100; $i++) {
    try { Invoke-WebRequest -Uri http://localhost:5000/traitement -UseBasicParsing | Out-Null }
    catch {}
    Start-Sleep -Milliseconds 200
}
```

---

## Tir de charge avec Apache Bench

```bash
# Dans la VM cible
sudo apt install apache2-utils -y

# Tir de charge : 1000 requêtes, 20 en parallèle
ab -n 1000 -c 20 http://192.168.56.10:5000/traitement
```

### Résultats observés (3 tirs)

| Percentile | Tir 1 (-c 50, n=2000) | Tir 2 (-c 20, n=5000) | Tir 3 (-c 20, n=5000) |
|---|---|---|---|
| p50 | 279ms | 292ms | 286ms |
| p75 | 384ms | 404ms | 395ms |
| p90 | 454ms | 471ms | 467ms |
| p95 | 480ms | 492ms | 488ms |
| p99 | 504ms | 531ms | 508ms |
| Max | 581ms | 707ms | 635ms |

**Analyse** : La dégradation commence au p90. Le p95 reste stable autour de 480-490ms sur les trois tirs, bien en dessous du seuil d'alerte de 1s. Le goulot d'étranglement est applicatif (`random.uniform(0.1, 0.8)`) et non infrastructure.

### Requête Grafana pour observer la latence

```promql
histogram_quantile(0.95, rate(api_request_duration_seconds_bucket[1m]))
```

---

## Requêtes PromQL de référence

```promql
# 1. Taux de requêtes/seconde sur 5 min (par status_code)
rate(api_requests_total[5m])

# 2. Ratio d'erreurs HTTP 500 en %
rate(api_requests_total{status_code="500"}[5m])
  / rate(api_requests_total[5m]) * 100

# 3. Utilisation CPU VM cible
(1 - avg by(instance)(rate(node_cpu_seconds_total{mode="idle",instance="192.168.56.10:9100"}[2m]))) * 100

# 4. Latence p95 de l'API
histogram_quantile(0.95, rate(api_request_duration_seconds_bucket[5m]))

# 5. RAM disponible VM cible
node_memory_MemAvailable_bytes{instance="192.168.56.10:9100"}
```

---

## Configurer Kibana (première fois)

1. Ouvrir http://localhost:5601 → ignorer "Your data is not secure" (Dismiss)
2. Menu hamburger → **Stack Management** → **Data Views** → **Create data view**
   - Name : `fastapi-logs`
   - Index pattern : `fastapi-logs-*`
   - Timestamp field : `@timestamp`
3. **Save data view to Kibana**
4. Menu hamburger → **Analytics** → **Discover** → sélectionner `fastapi-logs`

---

## Explication du filtre Grok ligne par ligne

Le filtre parse cette ligne brute Uvicorn :
```
INFO:     192.168.56.10:45322 - "GET /traitement HTTP/1.1" 200 OK
```

| Pattern | Rôle |
|---|---|
| `%{LOGLEVEL:loglevel}` | Capture `INFO`/`WARNING`/`ERROR` → champ `loglevel` |
| `:\s+` | Consume les deux-points et espaces — non capturé |
| `%{IP:client_ip}` | Capture l'adresse IPv4 → champ `client_ip` |
| `:%{NUMBER}` | Consume le port client (`:45322`) — ignoré |
| `\s+-\s+` | Consume le séparateur ` - ` |
| `\"%{WORD:method}` | Capture `GET`/`POST` → champ `method` |
| `\s+%{URIPATHPARAM:request}` | Capture `/traitement` → champ `request` |
| `\s+HTTP/%{NUMBER}\"` | Consume la version HTTP — ignorée |
| `\s+%{NUMBER:response_code}` | Capture `200`/`307`/`500` → champ `response_code` |

`tag_on_failure => ["_grokparsefailure_fastapi"]` : si une ligne ne correspond pas au pattern, elle est quand même stockée avec ce tag pour identification dans Kibana.

---

## Crash-tests (Chaos Engineering)

### Incident 1 — Panne applicative (InstanceDown)

```bash
vagrant ssh cible
sudo systemctl stop api-fastapi
# Surveiller http://localhost:9090/alerts
# Cycle : Inactive → Pending (1 min) → Firing
sudo systemctl start api-fastapi
```

### Incident 2 — Panne réseau (blocage port UFW)

```bash
vagrant ssh cible
# Bloquer le scrape Prometheus sur Node Exporter
sudo iptables -I INPUT -p tcp --dport 9100 -s 192.168.56.20 -j DROP
# → node-cible passe DOWN dans Prometheus
# → InstanceDown : Pending → Firing après 1 min
# → Kibana : aucun impact (Filebeat utilise le port 5044, pas 9100)

# Rétablir
sudo iptables -D INPUT -p tcp --dport 9100 -s 192.168.56.20 -j DROP
sudo ufw allow proto tcp from 192.168.56.20 to any port 9100
```

### Incident 3 — Saturation RAM

```bash
vagrant ssh cible
# Allouer 1 Go progressivement (100 Mo toutes les 15s)
python3 -c "
import time
x = []
for i in range(10):
    x.append(' ' * 100000000)
    print(f'Alloué {(i+1)*100} Mo')
    time.sleep(15)
time.sleep(60)
"
# Observer node_memory_MemAvailable_bytes dans Prometheus
# La courbe descend en escalier de ~1.6 Go → ~600 Mo
```

**Limite identifiée** : aucune alerte RAM n'est configurée dans `alert.rules.yml`. En production, ajouter :
```yaml
- alert: MemoryCritique
  expr: node_memory_MemAvailable_bytes < 500000000
  for: 1m
  labels:
    severity: critical
```

---

## Questions clés du rapport

### Pull vs Push
**Prometheus (Pull)** : Prometheus interroge les cibles toutes les 15s. Configuration centralisée, détection naturelle des pannes. Vulnérable au blocage pare-feu côté cible.

**Filebeat/Logstash (Push)** : Filebeat envoie dès qu'un log apparaît. Résilient (bufferisation locale), fonctionne derrière un pare-feu. Configuration distribuée sur chaque agent.

### Si Elasticsearch crash
Filebeat maintient un registre (`/var/lib/filebeat/registry`) de sa position dans chaque fichier. Logstash bufferise en attente. Dès le retour d'Elasticsearch, tous les événements en attente sont indexés. **Les logs ne sont pas perdus** pour des pannes courtes à moyennes.

### Middleware FastAPI — calcul de durée
```python
start_time = time.time()           # Début
response = await call_next(request) # Traitement (ex: 3 secondes)
duration = time.time() - start_time # Durée = 3.0s
api_request_duration_seconds.labels(...).observe(duration)  # Stocké dans histogram
```
Une durée de 3s incrémente les buckets `le="5.0"` et `le="+Inf"`, ainsi que `_sum` (+3.0) et `_count` (+1).

---

## Structure du projet

```
tp-elk/
├── Vagrantfile
├── app/
│   ├── app.py                  ← FastAPI + middleware Prometheus
│   ├── requirements.txt
│   └── api-fastapi.service     ← Unité systemd
└── ansible/
    ├── playbook-cible.yml      ← VM 1 : node_exporter + fastapi + ufw + filebeat
    ├── playbook-monitoring.yml ← VM 2 : prometheus + grafana + ELK
    ├── alert.rules.yml         ← 4 règles d'alerte
    └── roles/
        ├── node_exporter/
        ├── fastapi_app/
        ├── ufw/
        ├── filebeat/
        ├── prometheus/
        ├── grafana/
        ├── elasticsearch/
        ├── logstash/           ← pipeline Grok
        └── kibana/
```

---

## Dépannage fréquent

| Symptôme | Cause | Diagnostic |
|---|---|---|
| Kibana timeout | Elasticsearch pas encore prêt | Attendre 2-3 min, `systemctl status elasticsearch` |
| Filebeat ne se connecte pas | Logstash pas démarré | `systemctl status logstash` sur VM 2 |
| Target DOWN dans Prometheus | UFW ou iptables bloque | `sudo ufw status` + `sudo iptables -L INPUT -n` sur VM 1 |
| Logs vides dans Kibana | Filebeat ne lit pas le fichier | Vérifier `/var/log/api-fastapi.log` existe et contient des données |
| Grok parse failure | Format de log inattendu | Chercher `_grokparsefailure_fastapi` dans Kibana Discover |
| Elasticsearch doublon de config | `blockinfile` ajoute au lieu de remplacer | `sudo grep -n "xpack.security.enabled" /etc/elasticsearch/elasticsearch.yml` puis réécrire le fichier |
| Index `logs-fastapi-*` refusé | Conflit avec data stream ES8 | Renommer l'index en `fastapi-logs-*` dans `logstash.conf` |