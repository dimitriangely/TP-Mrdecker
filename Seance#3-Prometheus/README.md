# TP Observabilité — Prometheus, Grafana & Alertmanager

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Machine hôte Windows                                                │
│  localhost:9090 → Prometheus UI                                      │
│  localhost:3000 → Grafana UI                                         │
│  localhost:5000 → Flask API                                          │
│  localhost:9093 → Alertmanager UI                                    │
└────────────┬────────────────────────────────────────────────────────┘
             │ VirtualBox / réseau privé 192.168.56.0/24
    ┌────────┴────────────┐              ┌──────────────────────┐
    │  VM monitoring      │  pull :9100  │     VM target        │
    │  192.168.56.10      │◄─────────────│  192.168.56.20       │
    │                     │              │                      │
    │  • Prometheus :9090 │              │  • Node Exporter     │
    │  • Grafana    :3000 │              │    (métriques sys)   │
    │  • Node Exporter    │              └──────────────────────┘
    │  • Flask API  :5000 │
    │  • Alertmanager     │
    └─────────────────────┘
```

**Principe Pull de Prometheus** : c'est Prometheus qui va *chercher* les métriques
chez les exporters toutes les 15 secondes. Les cibles n'envoient rien elles-mêmes.

---

## Prérequis

- VirtualBox ≥ 6.1
- Vagrant ≥ 2.3
- Connexion Internet (téléchargement des binaires lors du provisioning)

---

## Démarrage rapide

```powershell
# 1. Se placer dans le répertoire
cd tp-observabilite

# 2. Démarrer les deux VMs (long au premier lancement : téléchargement box + provisioning)
vagrant up

# 3. Reprovisioner une seule VM si besoin
vagrant provision monitoring
vagrant provision target

# 4. Accéder aux interfaces
# Prometheus   : http://localhost:9090
# Grafana      : http://localhost:3000  (admin / admin123)
# Flask API    : http://localhost:5000
# Alertmanager : http://localhost:9093

# 5. Arrêter sans détruire
vagrant halt

# 6. Détruire complètement
vagrant destroy -f
```

---

## Vérifications manuelles (dans la VM)

```bash
vagrant ssh monitoring

# Node Exporter répond ?
curl -s http://localhost:9100/metrics | head -20

# Prometheus scrape ses cibles ?
curl -s http://localhost:9090/api/v1/targets | python3 -m json.tool

# Grafana tourne ?
systemctl status grafana-server

# Flask API répond ?
curl http://localhost:5000
curl http://localhost:5000/metrics

# Alertmanager actif ?
systemctl status alertmanager
curl http://localhost:9093
```

---

## Configurer Grafana (première fois)

1. Ouvrir http://localhost:3000 → login `admin` / `admin123`
2. **Ajouter une datasource** : Connections → Data Sources → Add → Prometheus
   - URL : `http://localhost:9090`
   - Cliquer **Save & Test** → doit afficher "Data source is working"
3. **Importer un dashboard** : Dashboards → Import → uploader le JSON téléchargé depuis
   `https://grafana.com/api/dashboards/1860/revisions/latest/download`
   *(L'import par ID ne fonctionne pas si la VM n'a pas accès à grafana.com)*

---

## Générer du trafic sur l'API Flask

```powershell
# Depuis PowerShell — envoyer 50 requêtes sur /traitement
for ($i=0; $i -lt 50; $i++) {
    try { Invoke-WebRequest -Uri http://localhost:5000/traitement -UseBasicParsing | Out-Null }
    catch {}
    Start-Sleep -Milliseconds 300
}
```

---

## Requêtes PromQL de référence

```promql
# Taux de requêtes/seconde sur 5 min (par status_code)
rate(api_requests_total[5m])

# Ratio d'erreurs HTTP 500 en %
rate(api_requests_total{status_code="500"}[5m])
  / rate(api_requests_total[5m]) * 100

# Temps de réponse moyen de l'API
rate(api_request_duration_seconds_sum[5m])
  / rate(api_request_duration_seconds_count[5m])

# RAM disponible en Go sur les VMs
node_memory_MemAvailable_bytes / 1024 / 1024 / 1024

# Utilisation CPU (%)
(1 - avg by(instance)(rate(node_cpu_seconds_total{mode="idle"}[2m]))) * 100
```

---

## Crash-tests Alertmanager

### Incident 1 — Panne applicative (InstanceDown)

```bash
vagrant ssh monitoring
sudo systemctl stop flask_app
# Surveiller http://localhost:9090/alerts
# Cycle : Inactive → Pending (1 min) → Firing
sudo systemctl start flask_app   # rétablissement
```

### Incident 2 — Surcharge CPU (CPUHigh)

```bash
vagrant ssh monitoring
sudo apt install stress-ng -y
sudo stress-ng --cpu 2 --timeout 180s &
# Surveiller http://localhost:9090/alerts
# CPUHigh passe Pending → Firing après 1 min à > 90% CPU
```

### Les 3 états d'une alerte

| État | Signification |
|---|---|
| **Inactive** | La condition `expr` est fausse — tout va bien |
| **Pending** | Condition vraie mais délai `for:` pas encore écoulé |
| **Firing** | Condition vraie depuis plus de `for:` — alerte active envoyée à Alertmanager |

---

## Structure du projet

```
tp-observabilite/
├── Vagrantfile
├── app/
│   ├── app.py                  # API Flask instrumentée (Counter + Histogram)
│   ├── requirements.txt        # flask + prometheus_client
│   └── flask_app.service       # Unité systemd
└── ansible/
    ├── playbook-monitoring.yml # VM monitoring : stack complète
    ├── playbook-target.yml     # VM target     : Node Exporter uniquement
    ├── alert.rules.yml         # Règles d'alerte (InstanceDown, CodeErreurHaut, CPUHigh)
    └── roles/
        ├── node_exporter/
        │   ├── defaults/main.yml
        │   ├── tasks/main.yml
        │   └── handlers/main.yml
        ├── prometheus/
        │   ├── defaults/main.yml
        │   ├── tasks/main.yml
        │   ├── handlers/main.yml
        │   └── templates/prometheus.yml.j2
        ├── grafana/
        │   ├── defaults/main.yml
        │   ├── tasks/main.yml
        │   └── handlers/main.yml
        ├── flask_app/
        │   ├── defaults/main.yml
        │   ├── tasks/main.yml
        │   └── handlers/main.yml
        └── alertmanager/
            ├── defaults/main.yml
            ├── tasks/main.yml
            ├── handlers/main.yml
            └── templates/alertmanager.yml.j2
```

---