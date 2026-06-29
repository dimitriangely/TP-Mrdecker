#!/usr/bin/env python3
"""
Exercice 4 — Stress test haute cardinalité
Injecte 5000 points/seconde dans flux_production
Chaque point a un piece_serial_number UUID unique (haute cardinalité)
"""

import uuid
import time
import random
import sys
import os
from influxdb_client_3 import InfluxDBClient3, Point

# -----------------------------------------------------------------------------
# Configuration — lire le token depuis le fichier
# -----------------------------------------------------------------------------
TOKEN_FILE = "/etc/influxdb3/admin_token.txt"

def read_token():
    try:
        with open(TOKEN_FILE, "r") as f:
            return f.read().strip()
    except PermissionError:
        # Essayer via sudo cat si permission refusée
        import subprocess
        result = subprocess.run(
            ["sudo", "cat", TOKEN_FILE],
            capture_output=True, text=True
        )
        return result.stdout.strip()

TOKEN    = read_token()
HOST     = "http://127.0.0.1:8086"
DATABASE = "usine_analytics"

BATCH_SIZE    = 500    # points par batch
TARGET_RPS    = 5000   # points par seconde cible
LIGNES        = ["L1", "L2", "L3", "L4", "L5"]
OPERATEURS    = ["Alice", "Bob", "Charlie", "Diana", "Eric"]

# -----------------------------------------------------------------------------
# Client InfluxDB v3
# -----------------------------------------------------------------------------
client = InfluxDBClient3(
    host=TOKEN and HOST,
    database=DATABASE,
    token=TOKEN,
)

# -----------------------------------------------------------------------------
# Boucle principale
# -----------------------------------------------------------------------------
print(f"Démarrage du stress test — cible: {TARGET_RPS} points/sec")
print(f"Base: {DATABASE} | Batch: {BATCH_SIZE} points")
print("Ctrl+C pour arrêter\n")

total_points = 0
start_global = time.time()

try:
    while True:
        batch_start = time.time()
        points = []

        for _ in range(BATCH_SIZE):
            point = (
                Point("flux_production")
                .tag("ligne_id", random.choice(LIGNES))
                .tag("operateur", random.choice(OPERATEURS))
                .tag("piece_serial_number", str(uuid.uuid4()))  # haute cardinalité
                .field("vitesse", random.randint(0, 150))
                .field("temperature", round(random.uniform(60.0, 95.0), 2))
                .field("erreur_critique", random.random() < 0.02)  # 2% d'erreurs
            )
            points.append(point)

        client.write(record=points)
        total_points += BATCH_SIZE

        elapsed = time.time() - batch_start
        elapsed_global = time.time() - start_global
        rps_current = BATCH_SIZE / elapsed if elapsed > 0 else 0
        rps_global  = total_points / elapsed_global if elapsed_global > 0 else 0

        print(
            f"Total: {total_points:>8} pts | "
            f"Batch: {rps_current:>6.0f} pts/s | "
            f"Moyenne: {rps_global:>6.0f} pts/s"
        )

        # Throttling pour atteindre TARGET_RPS
        target_duration = BATCH_SIZE / TARGET_RPS
        sleep_time = target_duration - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)

except KeyboardInterrupt:
    elapsed_global = time.time() - start_global
    print(f"\nArrêt — {total_points} points injectés en {elapsed_global:.1f}s")
    print(f"Débit moyen : {total_points/elapsed_global:.0f} pts/s")

finally:
    client.close()
