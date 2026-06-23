# Fichiers de service systemd — VM 1 (cible)

Ce document décrit où et comment les unités systemd sont créées et gérées sur la **VM 1** (`192.168.56.10`, hostname `cible`) dans le projet **tp-elk**.

---

## Vue d'ensemble

La VM 1 exécute trois services supervisés par systemd :

| Service | Rôle |
|---------|------|
| `api-fastapi` | API FastAPI instrumentée (métriques Prometheus, logs Uvicorn) |
| `node_exporter` | Export des métriques système (CPU, RAM, disque…) |
| `filebeat` | Agent de collecte de logs vers Logstash (VM 2) |

Ces services sont déployés par Ansible via `ansible/playbook-cible.yml`, déclenché au `vagrant up cible`.

### Chaîne de déploiement

```
vagrant up cible
    └── ansible_local → ansible/playbook-cible.yml
            ├── rôle node_exporter   → /etc/systemd/system/node_exporter.service
            ├── rôle fastapi_app     → /etc/systemd/system/api-fastapi.service
            ├── rôle ufw             (pas de service custom)
            └── rôle filebeat        → active le service du paquet APT
```

---

## Récapitulatif des fichiers

| Service systemd | Chemin sur la VM | Origine dans le dépôt |
|-----------------|------------------|------------------------|
| `api-fastapi` | `/etc/systemd/system/api-fastapi.service` | `app/api-fastapi.service` |
| `node_exporter` | `/etc/systemd/system/node_exporter.service` | Généré inline dans `ansible/roles/node_exporter/tasks/main.yml` |
| `filebeat` | `/lib/systemd/system/filebeat.service` (paquet Debian) | Installé via APT — pas de fichier custom dans le projet |

---

## 1. `api-fastapi.service`

### Fichiers concernés

| Fichier | Rôle |
|---------|------|
| `app/api-fastapi.service` | Modèle source (monté dans la VM via Vagrant à `/vagrant/app/`) |
| `ansible/roles/fastapi_app/tasks/main.yml` | Copie le fichier vers `/etc/systemd/system/` et démarre le service |
| `ansible/roles/fastapi_app/defaults/main.yml` | Variables (`fastapi_port`, `fastapi_dir`, `fastapi_user`, `fastapi_log`) |
| `ansible/roles/fastapi_app/handlers/main.yml` | Handler `restart fastapi` |

### Déploiement Ansible

```yaml
# ansible/roles/fastapi_app/tasks/main.yml
- name: "fastapi | Déployer le service systemd"
  ansible.builtin.copy:
    src: /vagrant/app/api-fastapi.service
    dest: /etc/systemd/system/api-fastapi.service
    mode: "0644"
    remote_src: true
  notify: restart fastapi

- name: "fastapi | Activer et démarrer"
  ansible.builtin.systemd:
    name: api-fastapi
    enabled: true
    state: started
    daemon_reload: true
```

### Contenu du service

```ini
[Unit]
Description=FastAPI — TP Observabilité Avancée
After=network.target

[Service]
User=fastapi
WorkingDirectory=/opt/fastapi_app
ExecStart=/opt/fastapi_app/venv/bin/uvicorn app:app --host 0.0.0.0 --port 5000
Restart=on-failure
RestartSec=5s
StandardOutput=append:/var/log/api-fastapi.log
StandardError=append:/var/log/api-fastapi.log

[Install]
WantedBy=multi-user.target
```

### Points clés

- **Utilisateur** : `fastapi` (compte système sans shell, créé par Ansible)
- **Répertoire** : `/opt/fastapi_app` (code + virtualenv Python)
- **Port** : `5000` (écoute sur toutes les interfaces : `0.0.0.0`)
- **Logs** : redirigés vers `/var/log/api-fastapi.log` — fichier lu ensuite par Filebeat
- **Redémarrage** : automatique en cas d'échec (`Restart=on-failure`, délai 5 s)

---

## 2. `node_exporter.service`

### Fichiers concernés

| Fichier | Rôle |
|---------|------|
| `ansible/roles/node_exporter/tasks/main.yml` | Crée le fichier `.service` avec du contenu inline |
| `ansible/roles/node_exporter/defaults/main.yml` | Version, port, utilisateur, chemin du binaire |
| `ansible/roles/node_exporter/handlers/main.yml` | Handler `restart node_exporter` |

### Déploiement Ansible

Le service n'existe pas comme fichier séparé dans le dépôt : Ansible le génère directement sur la VM :

```yaml
# ansible/roles/node_exporter/tasks/main.yml
- name: "node_exporter | Créer le service systemd"
  ansible.builtin.copy:
    dest: /etc/systemd/system/node_exporter.service
    mode: "0644"
    content: |
      [Unit]
      Description=Prometheus Node Exporter
      After=network.target

      [Service]
      User=node_exporter
      ExecStart=/usr/local/bin/node_exporter \
        --web.listen-address=:9100
      Restart=on-failure
      RestartSec=5s

      [Install]
      WantedBy=multi-user.target
```

### Points clés

- **Utilisateur** : `node_exporter`
- **Binaire** : `/usr/local/bin/node_exporter` (téléchargé depuis GitHub, version `1.8.1`)
- **Port** : `9100` (métriques scrapées par Prometheus sur la VM 2)
- **Pas de fichier source `.service`** dans le dépôt — toute modification passe par le rôle Ansible

---

## 3. `filebeat.service`

### Fichiers concernés

| Fichier | Rôle |
|---------|------|
| `ansible/roles/filebeat/tasks/main.yml` | Installe le paquet APT et active le service |
| `ansible/roles/filebeat/templates/filebeat.yml.j2` | Configuration Filebeat (`/etc/filebeat/filebeat.yml`) |
| `ansible/roles/filebeat/defaults/main.yml` | Version Filebeat, hôte Logstash |

### Déploiement Ansible

Ansible **n'écrit pas** de fichier `.service` custom. Il installe le paquet `filebeat` depuis le dépôt Elastic 8.x, puis active le service fourni par le paquet :

```yaml
# ansible/roles/filebeat/tasks/main.yml
- name: "filebeat | Installer filebeat"
  ansible.builtin.apt:
    name: "filebeat={{ filebeat_version }}"
    state: present

- name: "filebeat | Activer et démarrer"
  ansible.builtin.systemd:
    name: filebeat
    enabled: true
    state: started
    daemon_reload: true
```

### Points clés

- **Unité systemd** : fournie par le paquet Debian (`filebeat` 8.14.1)
- **Configuration** : `/etc/filebeat/filebeat.yml` (template Jinja2, permissions `0600`)
- **Destination des logs** : Logstash sur `192.168.56.20:5044`
- **Source des logs** : `/var/log/api-fastapi.log` (fichier alimenté par le service `api-fastapi`)

---

## Vérification sur la VM

```bash
vagrant ssh cible

# État des trois services
systemctl status api-fastapi node_exporter filebeat

# Lister les unités custom dans /etc/systemd/system/
ls -la /etc/systemd/system/*.service

# Voir le contenu d'une unité
systemctl cat api-fastapi
systemctl cat node_exporter
systemctl cat filebeat
```

Commandes utiles pour le crash-test applicatif (voir `README.md`) :

```bash
sudo systemctl stop api-fastapi    # simuler une panne
sudo systemctl start api-fastapi   # rétablir
```

---

## Dépannage

| Symptôme | Cause probable | Action |
|----------|------------------|--------|
| `api-fastapi` ne démarre pas | Dépendances Python manquantes ou permissions | `journalctl -u api-fastapi -n 50` |
| Port 5000 inaccessible | Service arrêté ou UFW actif | `systemctl status api-fastapi` + `sudo ufw status` |
| Target DOWN `node-cible` dans Prometheus | `node_exporter` arrêté ou port 9100 bloqué | `systemctl status node_exporter` |
| Logs absents dans Kibana | Filebeat arrêté ou fichier log vide | `systemctl status filebeat` + `ls -la /var/log/api-fastapi.log` |
| Filebeat refuse de démarrer | Permissions sur `filebeat.yml` | Le fichier doit être en `0600` (géré par Ansible) |

---

## Ce qui n'est pas sur la VM 1

Les services systemd des rôles **Prometheus**, **Grafana**, **Elasticsearch**, **Logstash** et **Kibana** sont déployés sur la **VM 2 (monitoring)** via `ansible/playbook-monitoring.yml`. Ils ne concernent pas la VM cible.
