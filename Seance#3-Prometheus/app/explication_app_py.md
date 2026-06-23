# Explication détaillée du fichier `app.py`

## Introduction

Ce fichier `app.py` implémente une API Web simple basée sur Flask et instrumentée avec Prometheus.

L'objectif est de :

* Simuler une API métier.
* Générer des métriques exploitables par Prometheus.
* Visualiser ces métriques dans Grafana.
* Comprendre le fonctionnement du monitoring applicatif.

---

# Architecture générale

```text
Utilisateur
     │
     ▼
  Flask API
     │
     ├── /
     ├── /traitement
     └── /metrics
              │
              ▼
        Prometheus
              │
              ▼
           Grafana
```

Le fonctionnement est le suivant :

1. Les utilisateurs envoient des requêtes à l'API Flask.
2. L'API met à jour des métriques Prometheus.
3. Prometheus récupère régulièrement les métriques via `/metrics`.
4. Grafana interroge Prometheus et affiche les graphiques.

---

# Importation des bibliothèques

```python
import time
import random
```

Ces bibliothèques servent à :

* mesurer le temps d'exécution d'une requête ;
* générer des comportements aléatoires afin de simuler une vraie application.

---

```python
from flask import Flask, request
```

Flask est un framework Web Python permettant de créer rapidement une API HTTP.

Création de l'application :

```python
app = Flask(__name__)
```

---

```python
from prometheus_client import (
    Counter,
    Histogram,
    make_wsgi_app,
    CONTENT_TYPE_LATEST,
    generate_latest
)
```

Cette bibliothèque permet de créer et exposer des métriques Prometheus.

---

# Les métriques Prometheus

Deux métriques sont déclarées :

* un Counter ;
* un Histogram.

---

# Métrique n°1 : Counter

```python
api_requests_total = Counter(
    'api_requests_total',
    'Nombre total de requêtes reçues par l\'API',
    ['method', 'endpoint', 'status_code']
)
```

## Objectif

Compter le nombre total de requêtes reçues.

Cette métrique ne fait qu'augmenter.

Exemples :

```text
1
2
3
4
5
...
```

Elle ne redescend jamais.

---

## Labels utilisés

| Label       | Exemple     |
| ----------- | ----------- |
| method      | GET         |
| endpoint    | /           |
| endpoint    | /traitement |
| status_code | 200         |
| status_code | 500         |

---

## Exemple

```python
api_requests_total.labels(
    method="GET",
    endpoint="/traitement",
    status_code="200"
).inc()
```

Le :

```python
.inc()
```

ajoute :

```text
+1
```

au compteur.

---

## Résultat visible dans Prometheus

```text
api_requests_total{
 method="GET",
 endpoint="/traitement",
 status_code="200"
} 150
```

Cela signifie :

```text
150 requêtes GET réussies sur /traitement
```

---

# Pourquoi utiliser un Counter ?

Un Counter est idéal pour :

* compter les requêtes ;
* compter les erreurs ;
* compter les connexions ;
* compter les événements.

Prometheus permet ensuite de calculer :

```promql
rate(api_requests_total[5m])
```

afin d'obtenir le nombre de requêtes par seconde.

---

# Métrique n°2 : Histogram

```python
api_request_duration_seconds = Histogram(
    'api_request_duration_seconds',
    'Durée des requêtes sur /traitement en secondes',
    buckets=[0.05, 0.1, 0.2, 0.3, 0.5, 0.8, 1.0, 2.0]
)
```

---

## Objectif

Mesurer les temps de réponse.

Exemples :

```text
0.12 s
0.18 s
0.35 s
0.72 s
```

---

## Les buckets

Les buckets représentent des intervalles de temps.

```python
[
 0.05,
 0.1,
 0.2,
 0.3,
 0.5,
 0.8,
 1.0,
 2.0
]
```

---

## Interprétation

| Bucket  | Signification       |
| ------- | ------------------- |
| <= 0.05 | moins de 50 ms      |
| <= 0.10 | moins de 100 ms     |
| <= 0.20 | moins de 200 ms     |
| <= 0.50 | moins de 500 ms     |
| <= 2.00 | moins de 2 secondes |

---

## Exemple

```python
api_request_duration_seconds.observe(0.35)
```

Prometheus incrémente automatiquement :

```text
<= 0.5
<= 0.8
<= 1.0
<= 2.0
```

---

# Pourquoi utiliser un Histogram ?

Il permet de calculer :

* le temps moyen ;
* le P50 ;
* le P95 ;
* le P99.

Exemple :

```promql
histogram_quantile(
  0.95,
  rate(api_request_duration_seconds_bucket[5m])
)
```

Cette requête retourne :

```text
Le temps de réponse du 95ème percentile.
```

Autrement dit :

```text
95 % des requêtes sont plus rapides que cette valeur.
```

---

# Route /

```python
@app.route('/')
def main():
```

Cette route correspond à :

```text
http://localhost:5000/
```

---

## Mise à jour du compteur

```python
api_requests_total.labels(
    method=request.method,
    endpoint='/',
    status_code='200'
).inc()
```

Le compteur est incrémenté.

---

## Réponse retournée

```python
return "Bienvenue sur l'API de test !"
```

Le navigateur affiche :

```text
Bienvenue sur l'API de test !
```

---

# Route /traitement

```python
@app.route('/traitement')
def traitement():
```

Cette route simule un traitement métier.

---

# Démarrage du chronomètre

```python
start = time.time()
```

Exemple :

```text
14:00:01.123
```

---

# Simulation d'un traitement

```python
time.sleep(random.uniform(0.1, 0.8))
```

Durée aléatoire :

```text
100 ms à 800 ms
```

Cela reproduit le comportement d'une application réelle.

---

# Simulation d'erreur

```python
if random.randint(1, 10) == 5:
```

Génère un nombre entre :

```text
1 et 10
```

Si le résultat vaut :

```text
5
```

une erreur est déclenchée.

---

## Taux d'erreur

```text
1 chance sur 10
```

soit :

```text
10 %
```

---

# Cas erreur HTTP 500

Mesure de la durée :

```python
duration = time.time() - start
```

---

Enregistrement du temps :

```python
api_request_duration_seconds.observe(duration)
```

---

Incrémentation du compteur :

```python
api_requests_total.labels(
    method=request.method,
    endpoint='/traitement',
    status_code='500'
).inc()
```

---

Retour :

```python
return "Erreur Interne", 500
```

Le client reçoit :

```http
HTTP/1.1 500 Internal Server Error
```

---

# Cas succès HTTP 200

Même principe :

```python
duration = time.time() - start
```

---

Enregistrement du temps :

```python
api_request_duration_seconds.observe(duration)
```

---

Incrémentation du compteur :

```python
api_requests_total.labels(
    method=request.method,
    endpoint='/traitement',
    status_code='200'
).inc()
```

---

Réponse :

```python
return "Traitement réussi !"
```

---

# Endpoint /metrics

```python
@app.route('/metrics')
def metrics():
```

Cette route expose les métriques à Prometheus.

---

## Fonctionnement

Prometheus appelle régulièrement :

```text
http://localhost:5000/metrics
```

---

Le serveur retourne :

```text
api_requests_total{method="GET",endpoint="/",status_code="200"} 25

api_requests_total{method="GET",endpoint="/traitement",status_code="200"} 180

api_requests_total{method="GET",endpoint="/traitement",status_code="500"} 20
```

---

Ainsi que :

```text
api_request_duration_seconds_bucket{le="0.1"} 12

api_request_duration_seconds_bucket{le="0.2"} 55

api_request_duration_seconds_bucket{le="0.5"} 130
```

---

# Modèle Pull de Prometheus

Prometheus ne reçoit pas les métriques.

C'est lui qui vient les chercher.

```text
Prometheus
      │
      ▼
GET /metrics
      │
      ▼
Récupération des métriques
      │
      ▼
Stockage dans la TSDB
      │
      ▼
Consultation via Grafana
```

---

# Démarrage de l'application

```python
if __name__ == '__main__':
```

Cette partie est exécutée lorsque l'on lance :

```bash
python app.py
```

---

Lancement du serveur :

```python
app.run(
    host='0.0.0.0',
    port=5000
)
```

---

## Signification

```text
0.0.0.0
```

signifie :

```text
Écouter sur toutes les interfaces réseau.
```

---

Le serveur est accessible via :

```text
http://localhost:5000
```

ou depuis une autre machine :

```text
http://IP_DU_SERVEUR:5000
```

---

# Requêtes PromQL utiles

## Nombre de requêtes par seconde

```promql
rate(api_requests_total[5m])
```

---

## Nombre total de requêtes

```promql
sum(api_requests_total)
```

---

## Nombre d'erreurs

```promql
sum(api_requests_total{status_code="500"})
```

---

## Pourcentage d'erreurs

```promql
(
  sum(rate(api_requests_total{status_code="500"}[5m]))
/
  sum(rate(api_requests_total[5m]))
) * 100
```

---

## Temps de réponse P95

```promql
histogram_quantile(
  0.95,
  rate(api_request_duration_seconds_bucket[5m])
)
```

---

# Conclusion

Cette application constitue un excellent exemple d'introduction au monitoring applicatif avec Prometheus.

Elle permet de comprendre :

* le fonctionnement d'une API Flask ;
* la création de métriques Prometheus ;
* l'utilisation des Counters ;
* l'utilisation des Histograms ;
* l'exposition des métriques via `/metrics` ;
* le fonctionnement du modèle Pull de Prometheus ;
* l'exploitation des métriques dans Grafana ;
* le calcul du débit, du taux d'erreur et des percentiles de latence.

Cette architecture est très proche de ce qui est utilisé en production dans les applications Web modernes.
