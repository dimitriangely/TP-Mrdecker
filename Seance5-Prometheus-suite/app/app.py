"""
app.py — API FastAPI instrumentée avec Prometheus via Middleware ASGI
TP Observabilité Avancée
"""
import time
import random
import logging
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import (
    Counter,
    Histogram,
    make_asgi_app,
    CONTENT_TYPE_LATEST,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Mount

# ── Configuration du logging structuré ───────────────────────────────────────
# Uvicorn écrit dans stdout/stderr → capturé par journald → lu par Filebeat
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(message)s"
)
logger = logging.getLogger(__name__)

# ── Déclaration des métriques Prometheus ──────────────────────────────────────

# Counter : nombre total de requêtes avec labels method, endpoint, status_code
# Pourquoi un Counter ? Une valeur strictement croissante.
# On calcule le taux via rate() dans PromQL.
api_requests_total = Counter(
    "api_requests_total",
    "Nombre total de requêtes HTTP reçues par l'API",
    ["method", "endpoint", "status_code"]
)

# Histogram : distribution des temps de réponse par method et endpoint
# Pourquoi un Histogram ? Permet de calculer des percentiles (p50, p95, p99)
# via histogram_quantile() — plus utile qu'une simple moyenne.
api_request_duration_seconds = Histogram(
    "api_request_duration_seconds",
    "Durée de traitement des requêtes HTTP en secondes",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
)

# ── Application FastAPI ───────────────────────────────────────────────────────
app = FastAPI(title="API FastAPI — TP Observabilité")

# ── Middleware d'instrumentation ──────────────────────────────────────────────
# Le middleware intercepte TOUTES les requêtes sans modifier les routes.
# C'est la méthode recommandée pour une instrumentation transverse.
@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    """
    Middleware qui mesure la durée de chaque requête et incrémente les compteurs.
    Avantage vs instrumentation par route : une seule implémentation pour toute l'API.
    """
    start_time = time.time()  # ← Cette ligne calcule le début de la durée

    # Appel de la route réelle
    response = await call_next(request)

    # Calcul de la durée réelle (après que la route a terminé)
    duration = time.time() - start_time  # ← La durée est calculée ici

    endpoint = request.url.path
    method   = request.method
    status   = str(response.status_code)

    # Incrémenter le Counter avec les labels
    api_requests_total.labels(
        method=method,
        endpoint=endpoint,
        status_code=status
    ).inc()

    # Observer la durée dans l'Histogram
    # La valeur est stockée dans les buckets Prometheus correspondants
    api_request_duration_seconds.labels(
        method=method,
        endpoint=endpoint
    ).observe(duration)

    # Log structuré Uvicorn (sera capturé par Filebeat)
    logger.info(
        f'{request.client.host} - "{method} {endpoint} HTTP/1.1" {status}'
    )

    return response

# ── Routes de l'API ───────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"message": "Bienvenue sur l'API FastAPI — TP Observabilité"}

@app.get("/traitement")
async def traitement():
    """Route qui simule un traitement de durée variable avec ~10% d'erreurs."""
    await __import__("asyncio").sleep(random.uniform(0.05, 0.5))

    if random.randint(1, 10) == 5:
        raise __import__("fastapi").HTTPException(
            status_code=500,
            detail="Erreur interne simulée"
        )
    return {"status": "ok", "message": "Traitement réussi"}

@app.get("/health")
async def health():
    """Endpoint de santé — utilisé par Prometheus pour la métrique 'up'."""
    return {"status": "healthy"}

# ── Endpoint /metrics (ASGI) ──────────────────────────────────────────────────
# make_asgi_app() crée une application ASGI compatible FastAPI
# Elle expose les métriques Prometheus au format texte sur /metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
