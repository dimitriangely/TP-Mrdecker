# TP InfluxDB v3 — Infrastructure as Code

## Environnement

| Composant | Version |
|---|---|
| OS | Ubuntu 22.04 LTS (ubuntu/jammy64) |
| InfluxDB | v3 Core 3.9.3 |
| Grafana | Stable (APT officiel) |
| Python | 3.10.12 |
| Vagrant | ansible_local |
| Ansible | 2.x (installé par Vagrant) |

## Architecture

```
Windows (Host)
└── VirtualBox
    └── VM Ubuntu 22.04 — influxdb-lab (192.168.56.10)
        ├── InfluxDB v3 Core  → port 8086
        └── Grafana           → port 3000
```

## Structure du projet

```
tp-influxdb-v3/
├── Vagrantfile
├── ansible.cfg
└── ansible/
    ├── playbook.yml              # master playbook
    ├── group_vars/
    │   └── all.yml               # variables globales
    ├── playbooks/
    │   ├── 01_influxdb.yml
    │   ├── 02_grafana.yml
    │   └── 03_data.yml
    └── roles/
        ├── influxdb/             # Ex 1, 2, 3
        ├── grafana/              # Ex 9
        └── influxdb_data/        # Ex 2, 4, 8
            └── files/
                ├── data_input.txt
                ├── stress_test.py
                └── downsample.py
```

## Démarrage rapide

```powershell
# Depuis D:\tp-influxdb-v3\
vagrant up
```

Le provisioning Ansible installe et configure automatiquement :
- InfluxDB v3 Core avec service systemd
- Token admin généré dans `/etc/influxdb3/admin_token.txt`
- Databases `usine_analytics` et `usine_historique_5ans`
- Grafana avec datasource InfluxDB provisionnée
- Client Python `influxdb3-python`
- Ingestion initiale de `data_input.txt`
- Cron de downsampling horaire

## Accès

| Service | URL | Credentials |
|---|---|---|
| Grafana | http://localhost:3000 | admin / admin |
| InfluxDB API | http://localhost:8086 | Token dans `/etc/influxdb3/admin_token.txt` |

## Commandes de validation

### Récupérer le token

```bash
export TOKEN=$(sudo cat /etc/influxdb3/admin_token.txt)
```

### Vérifier les services

```bash
systemctl is-active influxdb3
systemctl is-active grafana-server
```

### Lister les databases

```bash
influxdb3 show databases --token $TOKEN --host http://127.0.0.1:8086
```

### Requête SQL de base (Ex 3)

```bash
influxdb3 query --token $TOKEN --host http://127.0.0.1:8086 \
  --database usine_analytics \
  "SELECT * FROM flux_production WHERE time >= NOW() - INTERVAL '15 MINUTES'"
```

### Agrégation temporelle — date_bin (Ex 6)

```bash
influxdb3 query --token $TOKEN --host http://127.0.0.1:8086 \
  --database usine_analytics \
  "SELECT date_bin(INTERVAL '5 minutes', time) AS bucket,
          AVG(temperature) AS temp_moy
   FROM flux_production
   GROUP BY bucket
   ORDER BY bucket"
```

### Écart-type par opérateur et heure (Ex 6)

```bash
influxdb3 query --token $TOKEN --host http://127.0.0.1:8086 \
  --database usine_analytics \
  "SELECT date_bin(INTERVAL '1 hour', time) AS heure,
          operateur,
          STDDEV(vitesse) AS ecart_type_vitesse
   FROM flux_production
   GROUP BY heure, operateur
   ORDER BY heure"
```

### Plan d'exécution — Data Skipping (Ex 7)

```bash
influxdb3 query --token $TOKEN --host http://127.0.0.1:8086 \
  --database usine_analytics \
  "EXPLAIN SELECT * FROM flux_production
   WHERE time >= NOW() - INTERVAL '15 MINUTES'"
```

Le plan révèle le `pruning_predicate` DataFusion :
```
time_max@0 >= <timestamp> → fichiers Parquet éliminés sans lecture
```

### Stress test haute cardinalité (Ex 4)

```bash
# Lancer en arrière-plan
python3 /home/vagrant/stress_test.py &

# Observer la RAM (stable malgré les UUID uniques)
htop

# Observer l'apparition des fichiers Parquet
watch -n 10 'sudo find /var/lib/influxdb3/influxdb-lab-node -name "*.parquet" | wc -l'

# Arrêter
kill $(pgrep -f stress_test.py)
```

### Injecter des données manuellement (Ex 2)

```bash
curl -XPOST "http://localhost:8086/api/v3/write_lp?db=usine_analytics" \
  -H "Authorization: Bearer $TOKEN" \
  --data-binary @data_input.txt
```

### Test de rupture de type (Ex 2)

```bash
# Injection valide — vitesse en entier (i)
echo 'flux_production,ligne_id=L1,operateur=Test vitesse=100i,temperature=70.0' | \
  curl -XPOST "http://localhost:8086/api/v3/write_lp?db=usine_analytics" \
  -H "Authorization: Bearer $TOKEN" --data-binary @-

# Rupture de type — vitesse en float (doit retourner HTTP 400)
echo 'flux_production,ligne_id=L1,operateur=Test vitesse=100.5,temperature=70.0' | \
  curl -v -XPOST "http://localhost:8086/api/v3/write_lp?db=usine_analytics" \
  -H "Authorization: Bearer $TOKEN" --data-binary @-
```

### Downsampling manuel (Ex 8)

```bash
python3 /home/vagrant/downsample.py

# Vérifier les données agrégées
influxdb3 query --token $TOKEN --host http://127.0.0.1:8086 \
  --database usine_historique_5ans \
  "SELECT * FROM table_horaire LIMIT 10"
```

### Vérifier le cron

```bash
crontab -l -u vagrant
```

## Points techniques clés

### Pourquoi InfluxDB v3 tolère la haute cardinalité

Les versions v1/v2 maintenaient un index inversé en RAM (TSI — Time Series Index)
sur toutes les valeurs de tags vues. Des millions de tags uniques = explosion RAM.

En v3, le stockage est colonnaire Parquet — les tags sont des colonnes ordinaires,
pas des clés d'index. La RAM ne contient que le WAL actif (tampon d'écriture).

R�sultats observés dans ce TP :
- 93 000+ points avec UUID uniques injectés
- RAM InfluxDB stable à ~76 Mo
- Aucune pression mémoire (Swap = 0)

### Pipeline WAL → Parquet

```
Écriture → WAL (fichiers .wal séquentiels)
         → flush automatique (seuil volume)
         → fichiers .parquet (stockage final colonnaire)
```

### Data Skipping avec Apache Arrow DataFusion

Chaque fichier Parquet embarque des métadonnées Min/Max par colonne.
Le moteur lit ces métadonnées AVANT d'ouvrir les fichiers et élimine
ceux dont les valeurs ne peuvent pas satisfaire le prédicat de la requête.

Visible dans EXPLAIN avec :
```
pruning_predicate=time_max@0 >= <timestamp>
```

### Architecture hot/cold

Le moteur gère deux sources simultanément :
- DataSourceExec → fichiers Parquet (données froides)
- RecordBatchesExec → WAL en mémoire (données chaudes)

Union + DeduplicateExec assure la cohérence.

### Note sur TIME_BUCKET

Le sujet mentionne `TIME_BUCKET` — la fonction réelle dans DataFusion est `date_bin`.
Comportement identique, syntaxe différente :

```sql
-- Sujet TP
TIME_BUCKET(INTERVAL '5 MINUTES', time)

-- Syntaxe réelle InfluxDB v3 Core 3.9.3
date_bin(INTERVAL '5 minutes', time)
```

## Difficultés rencontrées et solutions

| Problème | Cause | Solution |
|---|---|---|
| `libpython3.13` manquante | Ubuntu 22.04 embarque Python 3.10 | PPA deadsnakes |
| `--node-id` obligatoire | Requis depuis v3.x | Ajout dans le service systemd |
| Token vide capturé | Codes ANSI dans stdout de la CLI | `sed 's/\x1b\[[0-9;]*m//g'` avant grep |
| `TIME_BUCKET` invalide | Fonction Enterprise / ancienne syntaxe | Remplacer par `date_bin` |
| `group_vars` ignorées | `/vagrant` world-writable | Variables passées via `extra_vars` Vagrant |

