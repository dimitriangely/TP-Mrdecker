# Tests de Validation — TP InfluxDB v3

Ce document liste l'ensemble des tests à exécuter pour valider chaque exercice
du TP. Chaque test indique la commande, le résultat attendu, et le statut observé.

---

## Prérequis — Récupérer le token

```bash
export TOKEN=$(sudo cat /etc/influxdb3/admin_token.txt)
echo "Token : $TOKEN"
```

**Résultat attendu** : affiche un token de la forme `apiv3_xxx...`

---

## Exercice 1 — Installation InfluxDB v3

### T01 — Binaire installé et version correcte

```bash
influxdb3 --version
```

**Résultat attendu** :
```
influxdb3 InfluxDB 3 Core, 3.9.3, revision e8cd4f7262c40eea9702ae97870480fdfdd76fa1
```

---

### T02 — Service systemd actif

```bash
systemctl is-active influxdb3
```

**Résultat attendu** :
```
active
```

---

### T03 — Service démarré automatiquement au boot

```bash
systemctl is-enabled influxdb3
```

**Résultat attendu** :
```
enabled
```

---

### T04 — API HTTP répond sur le port 8086

```bash
curl -s -o /dev/null -w "%{http_code}" \
  http://127.0.0.1:8086/health \
  -H "Authorization: Bearer $TOKEN"
```

**Résultat attendu** :
```
200
```

---

### T05 — Répertoire de données créé

```bash
sudo ls -la /var/lib/influxdb3/
```

**Résultat attendu** : répertoire appartenant à `influxdb3:influxdb3`

---

### T06 — Token admin sauvegardé

```bash
sudo test -s /etc/influxdb3/admin_token.txt && echo "OK" || echo "ERREUR"
```

**Résultat attendu** :
```
OK
```

---

### T07 — Databases créées

```bash
influxdb3 show databases \
  --token $TOKEN \
  --host http://127.0.0.1:8086
```

**Résultat attendu** :
```
+-----------------------+
| iox::database         |
+-----------------------+
| _internal             |
| usine_analytics       |
| usine_historique_5ans |
+-----------------------+
```

---

## Exercice 2 — Ingestion Line Protocol

### T08 — Données initiales présentes dans usine_analytics

```bash
influxdb3 query \
  --token $TOKEN \
  --host http://127.0.0.1:8086 \
  --database usine_analytics \
  "SELECT COUNT(*) FROM flux_production"
```

**Résultat attendu** : `count(*) >= 3` (données de data_input.txt injectées)

---

### T09 — Typage strict — test de rupture de type

```bash
# Injection valide (vitesse en entier avec suffixe i)
echo 'flux_production,ligne_id=LX,operateur=Test vitesse=100i,temperature=70.0,erreur_critique=f' | \
  curl -s -o /dev/null -w "%{http_code}" \
  -XPOST "http://127.0.0.1:8086/api/v3/write_lp?db=usine_analytics" \
  -H "Authorization: Bearer $TOKEN" \
  --data-binary @-
```

**Résultat attendu** : `204`

```bash
# Rupture de type (vitesse en float sans suffixe i)
echo 'flux_production,ligne_id=LX,operateur=Test vitesse=100.5,temperature=70.0,erreur_critique=f' | \
  curl -s -o /dev/null -w "%{http_code}" \
  -XPOST "http://127.0.0.1:8086/api/v3/write_lp?db=usine_analytics" \
  -H "Authorization: Bearer $TOKEN" \
  --data-binary @-
```

**Résultat attendu** : `400` (conflit de type détecté par le moteur Rust)

---

## Exercice 3 — Requêtage SQL

### T10 — Requête SELECT basique

```bash
influxdb3 query \
  --token $TOKEN \
  --host http://127.0.0.1:8086 \
  --database usine_analytics \
  "SELECT DISTINCT ligne_id FROM flux_production"
```

**Résultat attendu** : liste des lignes distinctes (L1, L2, L3...)

---

### T11 — Filtre temporel WHERE time

```bash
influxdb3 query \
  --token $TOKEN \
  --host http://127.0.0.1:8086 \
  --database usine_analytics \
  "SELECT * FROM flux_production WHERE time >= NOW() - INTERVAL '15 MINUTES' LIMIT 5"
```

**Résultat attendu** : lignes avec timestamp dans les 15 dernières minutes

---

## Exercice 4 — Stress test haute cardinalité

### T12 — Script stress_test.py déployé et exécutable

```bash
test -x /home/vagrant/stress_test.py && echo "OK" || echo "ERREUR"
```

**Résultat attendu** :
```
OK
```

---

### T13 — Client Python influxdb3-python installé

```bash
python3 -c "import influxdb_client_3; print('OK')"
```

**Résultat attendu** :
```
OK
```

---

### T14 — Lancement du stress test

```bash
python3 /home/vagrant/stress_test.py &
sleep 5
ps aux | grep -v grep | grep stress_test | awk '{print "PID:", $2, "— Statut: actif"}'
```

**Résultat attendu** : ligne affichant le PID du processus actif

---

### T15 — RAM InfluxDB stable sous charge

```bash
# Lire la RAM du processus influxdb3 en Mo
ps -o pid,rss,comm -p $(pgrep influxdb3) | \
  awk 'NR>1 {printf "RAM influxdb3 : %.1f Mo\n", $2/1024}'
```

**Résultat attendu** : valeur inférieure à 200 Mo malgré les millions de tags UUID uniques

---

### T16 — Arrêt propre du stress test

```bash
kill $(pgrep -f stress_test.py) 2>/dev/null
sleep 2
ps aux | grep -v grep | grep stress_test && echo "ERREUR: toujours actif" || echo "OK: arrêté"
```

**Résultat attendu** :
```
OK: arrêté
```

---

## Exercice 5 — Fichiers WAL et Parquet

### T17 — Fichiers WAL générés

```bash
sudo ls /var/lib/influxdb3/influxdb-lab-node/wal/ | wc -l
```

**Résultat attendu** : nombre > 0 (fichiers .wal présents)

---

### T18 — Taille totale des WAL

```bash
sudo du -sh /var/lib/influxdb3/influxdb-lab-node/wal/
```

**Résultat attendu** : taille cohérente avec le volume injecté (plusieurs Mo après stress test)

---

### T19 — Apparition des fichiers Parquet après flush

```bash
# Relancer le stress test pour accumuler du volume
python3 /home/vagrant/stress_test.py &
# Attendre le flush automatique (5-15 minutes selon le volume)
sleep 60
sudo find /var/lib/influxdb3/influxdb-lab-node -name "*.parquet" | wc -l
```

**Résultat attendu** : nombre > 0 après accumulation suffisante de données

---

## Exercice 6 — Requêtes analytiques avancées

### T20 — Agrégation temporelle avec date_bin (équivalent TIME_BUCKET)

```bash
influxdb3 query \
  --token $TOKEN \
  --host http://127.0.0.1:8086 \
  --database usine_analytics \
  "SELECT date_bin(INTERVAL '5 minutes', time) AS bucket,
          AVG(temperature) AS temp_moy
   FROM flux_production
   GROUP BY bucket
   ORDER BY bucket"
```

**Résultat attendu** : tableau avec colonnes `bucket` et `temp_moy` par tranches de 5 minutes

---

### T21 — Écart-type de la vitesse par opérateur et heure

```bash
influxdb3 query \
  --token $TOKEN \
  --host http://127.0.0.1:8086 \
  --database usine_analytics \
  "SELECT date_bin(INTERVAL '1 hour', time) AS heure,
          operateur,
          STDDEV(vitesse) AS ecart_type_vitesse
   FROM flux_production
   GROUP BY heure, operateur
   ORDER BY heure, operateur"
```

**Résultat attendu** : tableau avec écart-type par opérateur et tranche horaire

---

### T22 — Recherche d'un UUID spécifique

```bash
# Récupérer un UUID existant
UUID=$(influxdb3 query \
  --token $TOKEN \
  --host http://127.0.0.1:8086 \
  --database usine_analytics \
  "SELECT piece_serial_number FROM flux_production LIMIT 1" \
  2>/dev/null | grep -v "piece_serial_number\|---\|+--" | head -1 | tr -d '| ')

echo "UUID cible : $UUID"

# Mesurer le temps de recherche
time influxdb3 query \
  --token $TOKEN \
  --host http://127.0.0.1:8086 \
  --database usine_analytics \
  "SELECT * FROM flux_production WHERE piece_serial_number = '$UUID'"
```

**Résultat attendu** : 1 ligne retournée, temps d'exécution rapide grâce au Data Skipping

---

## Exercice 7 — Data Skipping avec EXPLAIN

### T23 — Plan d'exécution EXPLAIN visible

```bash
influxdb3 query \
  --token $TOKEN \
  --host http://127.0.0.1:8086 \
  --database usine_analytics \
  "EXPLAIN SELECT * FROM flux_production
   WHERE time >= NOW() - INTERVAL '15 MINUTES'"
```

**Résultat attendu** : plan contenant les éléments suivants :
- `logical_plan` avec `Filter` et `TableScan`
- `physical_plan` avec `DataSourceExec` (Parquet) et/ou `RecordBatchesExec` (WAL)
- `pruning_predicate` avec `time_max@0 >= <timestamp>` — preuve du Data Skipping

---

## Exercice 8 — Downsampling et Cron

### T24 — Script downsample.py déployé

```bash
test -x /home/vagrant/downsample.py && echo "OK" || echo "ERREUR"
```

**Résultat attendu** :
```
OK
```

---

### T25 — Cron configuré pour l'utilisateur vagrant

```bash
crontab -l -u vagrant
```

**Résultat attendu** :
```
0 * * * * /usr/bin/python3 /home/vagrant/downsample.py >> /var/log/influxdb_downsample.log 2>&1
```

---

### T26 — Exécution manuelle du downsampling

```bash
python3 /home/vagrant/downsample.py
echo "Exit code : $?"
```

**Résultat attendu** :
```
Downsampling usine_analytics → usine_historique_5ans
Downsampling terminé avec succès
Exit code : 0
```

---

### T27 — Données présentes dans la base historique

faire vagrant ssh puis :

```bash
cat >/home/vagrant/downsample.py <<'PY'
#!/usr/bin/env python3

import sys
import subprocess
import urllib.request
from influxdb_client_3 import InfluxDBClient3

TOKEN_FILE = "/etc/influxdb3/admin_token.txt"

def read_token():
    try:
        with open(TOKEN_FILE, "r") as f:
            return f.read().strip()
    except PermissionError:
        result = subprocess.run(
            ["sudo", "cat", TOKEN_FILE],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

def esc_tag(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(" ", "\\ ")
        .replace(",", "\\,")
        .replace("=", "\\=")
    )

TOKEN = read_token()
HOST = "http://127.0.0.1:8086"
DB_SRC = "usine_analytics"
DB_DST = "usine_historique_5ans"

QUERY = """
SELECT
    DATE_BIN(INTERVAL '1 hour', time) AS time,
    operateur,
    ligne_id,
    AVG(temperature) AS temperature_moy,
    MAX(vitesse) AS vitesse_max,
    MIN(vitesse) AS vitesse_min,
    COUNT(*) AS nb_points
FROM flux_production
WHERE time >= NOW() - INTERVAL '1 day'
GROUP BY 1, operateur, ligne_id
ORDER BY 1
"""

client = None

try:
    print(f"Downsampling {DB_SRC} → {DB_DST}")

    client = InfluxDBClient3(
        host=HOST,
        database=DB_SRC,
        token=TOKEN,
    )

    result = client.query(QUERY)
    rows = result.to_pylist()

    if not rows:
        print("Aucune donnée à agréger.")
        sys.exit(0)

    lines = []

    for row in rows:
        ts = int(row["time"].timestamp() * 1_000_000_000)

        lines.append(
            (
                f"table_horaire,"
                f"operateur={esc_tag(row['operateur'])},"
                f"ligne_id={esc_tag(row['ligne_id'])} "
                f"temperature_moy={float(row['temperature_moy'])},"
                f"vitesse_max={float(row['vitesse_max'])},"
                f"vitesse_min={float(row['vitesse_min'])},"
                f"nb_points={int(row['nb_points'])}i "
                f"{ts}"
            )
        )

    payload = "\n".join(lines).encode("utf-8")

    req = urllib.request.Request(
        f"{HOST}/api/v3/write_lp?db={DB_DST}",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "text/plain",
        },
    )

    with urllib.request.urlopen(req) as response:
        response.read()

    print(f"Downsampling terminé : {len(lines)} lignes écrites.")

except Exception as e:
    print(f"Erreur lors du downsampling : {e}", file=sys.stderr)
    sys.exit(1)

finally:
    if client:
        client.close()
PY

chmod +x /home/vagrant/downsample.py
```
puis executé :

```bash
python3 /home/vagrant/downsample.py
```

vérifier que la table a été bien crée :

```bash
influxdb3 query \
  --token $TOKEN \
  --host http://127.0.0.1:8086 \
  --database usine_historique_5ans \
  "SHOW TABLES"
```
Puis affiche les données :

```bash
influxdb3 query \
  --token $TOKEN \
  --host http://127.0.0.1:8086 \
  --database usine_historique_5ans \
  "SELECT * FROM table_horaire LIMIT 10"
```

**Résultat attendu** : Downsampling terminé : 29 lignes écrites.

---

## Exercice 9 — Grafana

### T28 — Service Grafana actif

```bash
systemctl is-active grafana-server
```

**Résultat attendu** :
```
active
```

---

### T29 — API Grafana accessible

```bash
curl -s -o /dev/null -w "%{http_code}" \
  http://127.0.0.1:3000/api/health
```

**Résultat attendu** :
```
200
```

---

### T30 — Datasource InfluxDB provisionnée

```bash
curl -s \
  http://admin:admin@127.0.0.1:3000/api/datasources \
  | python3 -c "
import json, sys
ds = json.load(sys.stdin)
names = [d['name'] for d in ds]
print('Datasources:', names)
print('InfluxDB3-usine présente:', 'InfluxDB3-usine' in names)
"
```

**Résultat attendu** :
```
Datasources: ['InfluxDB3-usine']
InfluxDB3-usine présente: True
```

---

## Récapitulatif

| Test | Exercice | Description | Statut |
|------|----------|-------------|--------|
| T01 | Ex 1 | Version binaire influxdb3 | ✅ |
| T02 | Ex 1 | Service systemd actif | ✅ |
| T03 | Ex 1 | Service activé au boot | ✅ |
| T04 | Ex 1 | API HTTP port 8086 | ✅ |
| T05 | Ex 1 | Répertoire de données | ✅ |
| T06 | Ex 1 | Token admin sauvegardé | ✅ |
| T07 | Ex 1 | Databases créées | ✅ |
| T08 | Ex 2 | Données initiales injectées | ✅ |
| T09 | Ex 2 | Rupture de type HTTP 400 | ✅ |
| T10 | Ex 3 | SELECT DISTINCT | ✅ |
| T11 | Ex 3 | Filtre temporel WHERE time | ✅ |
| T12 | Ex 4 | stress_test.py déployé | ✅ |
| T13 | Ex 4 | Client Python installé | ✅ |
| T14 | Ex 4 | Stress test actif | ✅ |
| T15 | Ex 4 | RAM stable sous charge | ✅ |
| T16 | Ex 4 | Arrêt propre stress test | ✅ |
| T17 | Ex 5 | Fichiers WAL présents | ✅ |
| T18 | Ex 5 | Taille WAL cohérente | ✅ |
| T19 | Ex 5 | Fichiers Parquet après flush | ✅ |
| T20 | Ex 6 | Agrégation date_bin 5 min | ✅ |
| T21 | Ex 6 | Écart-type par opérateur | ✅ |
| T22 | Ex 6 | Recherche UUID spécifique | ✅ |
| T23 | Ex 7 | EXPLAIN + pruning_predicate | ✅ |
| T24 | Ex 8 | downsample.py déployé | ✅ |
| T25 | Ex 8 | Cron configuré | ✅ |
| T26 | Ex 8 | Downsampling manuel OK | ✅ |
| T27 | Ex 8 | Données dans base historique | ✅ |
| T28 | Ex 9 | Grafana actif | ✅ |
| T29 | Ex 9 | API Grafana accessible | ✅ |
| T30 | Ex 9 | Datasource provisionnée | ✅ |

**Total : 30 tests — 30 validés**