# Pipeline Logstash — `logstash.conf.j2`

Ce document explique le fichier `ansible/roles/logstash/templates/logstash.conf.j2`, template Jinja2 Ansible qui définit le **pipeline de traitement des logs** FastAPI sur la VM 2 (monitoring).

---

## Vue d'ensemble

Ce fichier configure Logstash pour :

1. **Recevoir** les logs envoyés par Filebeat (VM 1) sur le port Beats `5044`
2. **Parser** chaque ligne Uvicorn avec un filtre **Grok** en champs structurés
3. **Indexer** les événements dans Elasticsearch avec un index quotidien `logs-fastapi-YYYY.MM.dd`

Une fois déployé par Ansible, il devient sur la VM 2 :

```
/etc/logstash/conf.d/fastapi.conf
```

---

## Rôle dans l'architecture

C'est l'étape centrale du flux **push** des logs applicatifs :

```
VM 1 (cible — 192.168.56.10)          VM 2 (monitoring — 192.168.56.20)
─────────────────────────────          ───────────────────────────────────

FastAPI / Uvicorn
    ↓ écrit dans
/var/log/api-fastapi.log
    ↓ lu par Filebeat
    └──── push :5044 ──────────────→  Logstash (fastapi.conf)
                                          ↓ filtre Grok + mutate
                                      Elasticsearch :9200
                                          ↓
                                      Kibana :5601 (index logs-fastapi-*)
```

Le parsing Grok est réalisé **dans Logstash** (et non dans Filebeat). Filebeat se contente de lire le fichier et de transmettre les lignes brutes — d'où l'obligation de passer par Logstash dans ce TP.

---

## Fichiers liés

| Fichier | Rôle |
|---------|------|
| `ansible/roles/logstash/templates/logstash.conf.j2` | Template source (ce document) |
| `ansible/roles/logstash/tasks/main.yml` | Déploie le template vers `/etc/logstash/conf.d/fastapi.conf` |
| `ansible/roles/logstash/defaults/main.yml` | Variables par défaut (ports, hôte Elasticsearch) |
| `ansible/roles/filebeat/templates/filebeat.yml.j2` | Filebeat sur VM 1 — envoie vers Logstash `:5044` |
| `app/api-fastapi.service` | Redirige stdout/stderr Uvicorn vers `/var/log/api-fastapi.log` |

### Chaîne de déploiement

```
vagrant up monitoring
    └── ansible_local → ansible/playbook-monitoring.yml
            └── rôle logstash
                    └── template logstash.conf.j2 → /etc/logstash/conf.d/fastapi.conf
                    └── systemctl start logstash
```

---

## Variables Ansible injectées

Définies dans `ansible/roles/logstash/defaults/main.yml` :

| Variable | Valeur par défaut | Usage dans le template |
|----------|-------------------|------------------------|
| `logstash_beats_port` | `5044` | Port d'écoute du plugin `beats` (input) |
| `elasticsearch_host` | `localhost` | Hôte Elasticsearch (même VM) |
| `elasticsearch_port` | `9200` | Port Elasticsearch (output) |

---

## Structure du pipeline

Le fichier suit la structure standard Logstash en **trois sections** : `input` → `filter` → `output`.

### 1. `input` — réception depuis Filebeat

```ruby
input {
  beats {
    port => 5044
  }
}
```

- Écoute le protocole **Beats** sur le port `5044`
- Filebeat (VM 1) pousse les lignes lues dans `/var/log/api-fastapi.log`
- Chaque événement reçu contient notamment un champ `message` avec la ligne brute du log, ainsi que des métadonnées Filebeat (`service: api-fastapi`, `host_role: cible`)

---

### 2. `filter` — parsing et transformation

#### Filtre Grok

**Objectif :** transformer une ligne Uvicorn brute en champs exploitables dans Kibana.

**Exemple de ligne entrante :**

```
INFO:     192.168.56.10:45322 - "GET /traitement HTTP/1.1" 200 OK
```

**Pattern Grok appliqué sur le champ `message` :**

```
%{LOGLEVEL:loglevel}:\s+%{IP:client_ip}:%{NUMBER} - "%{WORD:method} %{URIPATHPARAM:request} HTTP/%{NUMBER}" %{NUMBER:response_code}
```

**Décomposition du pattern :**

| Partie du pattern | Champ extrait | Exemple |
|-------------------|---------------|---------|
| `%{LOGLEVEL:loglevel}` | `loglevel` | `INFO`, `WARNING`, `ERROR` |
| `:\s+` | — | `:` suivi d'espaces (`:     `) |
| `%{IP:client_ip}` | `client_ip` | `192.168.56.10` |
| `:%{NUMBER}` | *(non nommé)* | `:45322` (port client, ignoré) |
| `\s+-\s+` | — | ` - ` |
| `%{WORD:method}` | `method` | `GET`, `POST` |
| `%{URIPATHPARAM:request}` | `request` | `/traitement`, `/health` |
| `HTTP/%{NUMBER}` | — | `HTTP/1.1` |
| `%{NUMBER:response_code}` | `response_code` | `200`, `500` |

Le suffixe ` OK` en fin de ligne n'est pas capturé — ce n'est pas bloquant pour l'indexation.

**`tag_on_failure` :**

```ruby
tag_on_failure => ["_grokparsefailure_fastapi"]
```

Si une ligne ne correspond pas au pattern (stack trace Python, format inattendu), le log est **quand même stocké** dans Elasticsearch avec le tag `_grokparsefailure_fastapi`. Dans Kibana Discover, filtrer sur ce tag permet de détecter les formats non parsés.

#### Filtre `mutate`

```ruby
mutate {
  convert => { "response_code" => "integer" }
}
```

Convertit `response_code` de chaîne (`"200"`) en **entier** (`200`), ce qui permet les filtres numériques et agrégations dans Kibana (ex. « toutes les requêtes avec code ≥ 500 »).

---

### 3. `output` — envoi vers Elasticsearch

```ruby
output {
  elasticsearch {
    hosts => ["localhost:9200"]
    index => "logs-fastapi-%{+YYYY.MM.dd}"
  }
}
```

- **Destination :** Elasticsearch sur la même VM (`localhost:9200`)
- **Index :** un index par jour, par exemple `logs-fastapi-2025.06.23`
- **Data view Kibana :** pattern `logs-fastapi-*` (voir `README.md`)

---

## Exemple de transformation

**Avant (champ `message` brut) :**

```json
{
  "message": "INFO:     192.168.56.10:45322 - \"GET /traitement HTTP/1.1\" 200 OK",
  "service": "api-fastapi",
  "host_role": "cible"
}
```

**Après passage dans le pipeline :**

```json
{
  "message": "INFO:     192.168.56.10:45322 - \"GET /traitement HTTP/1.1\" 200 OK",
  "loglevel": "INFO",
  "client_ip": "192.168.56.10",
  "method": "GET",
  "request": "/traitement",
  "response_code": 200,
  "service": "api-fastapi",
  "host_role": "cible"
}
```

---

## Vérification

### Sur la VM monitoring

```bash
vagrant ssh monitoring

# Service Logstash actif ?
systemctl status logstash

# Pipeline déployé ?
cat /etc/logstash/conf.d/fastapi.conf

# Port Beats en écoute ?
ss -tlnp | grep 5044
```

### Dans Kibana

1. Ouvrir http://localhost:5601
2. **Discover** → data view `logs-fastapi-*`
3. Vérifier la présence des champs : `loglevel`, `client_ip`, `method`, `request`, `response_code`
4. Générer du trafic depuis Windows :

```powershell
for ($i=0; $i -lt 20; $i++) {
    Invoke-WebRequest -Uri http://localhost:5000/traitement -UseBasicParsing | Out-Null
    Start-Sleep -Milliseconds 200
}
```

### Détecter les échecs de parsing

Dans Kibana Discover, filtrer sur :

```
tags: _grokparsefailure_fastapi
```

---

## Dépannage

| Symptôme | Cause probable | Action |
|----------|------------------|--------|
| Logs absents dans Kibana | Logstash ou Elasticsearch arrêté | `systemctl status logstash elasticsearch` sur VM 2 |
| Filebeat ne se connecte pas | Logstash pas prêt (démarrage lent ~60s) | Attendre, vérifier `ss -tlnp \| grep 5044` |
| Champs Grok vides | Format de log différent du pattern Uvicorn | Chercher `_grokparsefailure_fastapi` dans Kibana |
| Index introuvable | Aucun log reçu ce jour | Vérifier le trafic API + chaîne Filebeat → Logstash |
| `response_code` en texte | Filtre `mutate` non appliqué | Vérifier que le pipeline complet est chargé (`fastapi.conf`) |

---

## Pourquoi Logstash et pas Filebeat seul ?

Filebeat peut envoyer directement vers Elasticsearch, mais dans ce TP :

- Le **parsing Grok** est centralisé dans Logstash (plus flexible, testable, réutilisable)
- Logstash peut appliquer des transformations supplémentaires (`mutate`, futurs enrichissements)
- La configuration Filebeat (`filebeat.yml.j2`) désigne explicitement `output.logstash` et non `output.elasticsearch`

Cela illustre le modèle **push** avec une couche de traitement intermédiaire entre l'agent et le stockage.
