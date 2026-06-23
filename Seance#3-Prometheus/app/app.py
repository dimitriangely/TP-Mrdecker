import time
import random
from flask import Flask, request
from prometheus_client import (
    Counter,
    Histogram,
    make_wsgi_app,
    CONTENT_TYPE_LATEST,
    generate_latest
)
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from flask import Response

app = Flask(__name__)

# ── Déclaration des métriques ─────────────────────────────────────────────────

# Counter : compte le nombre total de requêtes reçues
# Labels : method (GET/POST), endpoint (/traitement), status_code (200/500)
# Pourquoi un Counter ? Une valeur qui ne fait que croître — parfait pour
# compter des événements. On calcule le taux via rate() dans PromQL.
api_requests_total = Counter(
    'api_requests_total',
    'Nombre total de requêtes reçues par l\'API',
    ['method', 'endpoint', 'status_code']
)

# Histogram : mesure la distribution des temps de réponse
# Buckets : intervalles en secondes pour classer les durées
# Pourquoi un Histogram ? Permet de calculer des percentiles (p50, p95, p99)
# via histogram_quantile() dans PromQL, plus utile que juste une moyenne.
api_request_duration_seconds = Histogram(
    'api_request_duration_seconds',
    'Durée des requêtes sur /traitement en secondes',
    buckets=[0.05, 0.1, 0.2, 0.3, 0.5, 0.8, 1.0, 2.0]
)

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def main():
    api_requests_total.labels(
        method=request.method,
        endpoint='/',
        status_code='200'
    ).inc()
    return "Bienvenue sur l'API de test !"

@app.route('/traitement')
def traitement():
    start = time.time()

    # Simule un traitement de durée variable (0.1s à 0.8s)
    time.sleep(random.uniform(0.1, 0.8))

    if random.randint(1, 10) == 5:
        duration = time.time() - start
        api_request_duration_seconds.observe(duration)
        api_requests_total.labels(
            method=request.method,
            endpoint='/traitement',
            status_code='500'
        ).inc()
        return "Erreur Interne", 500

    duration = time.time() - start
    api_request_duration_seconds.observe(duration)
    api_requests_total.labels(
        method=request.method,
        endpoint='/traitement',
        status_code='200'
    ).inc()
    return "Traitement réussi !"

# ── Endpoint /metrics ─────────────────────────────────────────────────────────
# Prometheus viendra scraper cette URL toutes les 15 secondes (modèle Pull)

@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
