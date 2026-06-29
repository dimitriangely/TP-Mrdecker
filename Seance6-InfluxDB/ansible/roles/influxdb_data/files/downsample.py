#!/usr/bin/env python3
"""
Exercice 8 — Downsampling SQL via cron
Agrège les données brutes de usine_analytics par heure
et les insère dans usine_historique_5ans
Planifié toutes les heures via crontab
"""

import sys
import os
from influxdb_client_3 import InfluxDBClient3

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
TOKEN_FILE = "/etc/influxdb3/admin_token.txt"

def read_token():
    try:
        with open(TOKEN_FILE, "r") as f:
            return f.read().strip()
    except PermissionError:
        import subprocess
        result = subprocess.run(
            ["sudo", "cat", TOKEN_FILE],
            capture_output=True, text=True
        )
        return result.stdout.strip()

TOKEN    = read_token()
HOST     = "http://127.0.0.1:8086"
DB_SRC   = "usine_analytics"
DB_DST   = "usine_historique_5ans"

# -----------------------------------------------------------------------------
# Requête de downsampling
# Agrège par heure les données des dernières 24h
# -----------------------------------------------------------------------------
QUERY = f"""
INSERT INTO {DB_DST}.table_horaire
SELECT
    TIME_BUCKET(INTERVAL '1 HOUR', time) AS time,
    operateur,
    ligne_id,
    AVG(temperature)  AS temperature_moy,
    MAX(vitesse)      AS vitesse_max,
    MIN(vitesse)      AS vitesse_min,
    COUNT(*)          AS nb_points
FROM {DB_SRC}.flux_production
WHERE time >= NOW() - INTERVAL '1 DAY'
GROUP BY 1, operateur, ligne_id
"""

# -----------------------------------------------------------------------------
# Exécution
# -----------------------------------------------------------------------------
print(f"Downsampling {DB_SRC} → {DB_DST}")

try:
    client = InfluxDBClient3(
        host=HOST,
        database=DB_SRC,
        token=TOKEN,
    )

    client.query(QUERY)
    print("Downsampling terminé avec succès")

except Exception as e:
    print(f"Erreur lors du downsampling : {e}", file=sys.stderr)
    sys.exit(1)

finally:
    client.close()
