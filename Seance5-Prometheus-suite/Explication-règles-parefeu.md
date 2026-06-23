# Règles de pare-feu (UFW)

Ce document décrit où et comment les règles de pare-feu sont appliquées dans le projet **tp-elk**.

---

## Vue d'ensemble

Le pare-feu est configuré **uniquement sur la VM 1 (cible)** — `192.168.56.10` — via **UFW** (*Uncomplicated Firewall*). La VM 2 (monitoring) n'a pas de pare-feu Ansible dans ce projet.

**Objectif :** n'autoriser que la VM monitoring (`192.168.56.20`) à scraper les ports de supervision (`:9100` et `:5000`), tout en gardant l'accès SSH et l'accès à FastAPI depuis l'hôte Windows.

---

## Où sont définies les règles ?

| Fichier | Rôle |
|---------|------|
| `ansible/roles/ufw/tasks/main.yml` | Tâches Ansible qui installent et configurent UFW |
| `ansible/roles/ufw/defaults/main.yml` | IP de la VM monitoring autorisée (`monitoring_ip`) |
| `ansible/playbook-cible.yml` | Playbook qui inclut le rôle `ufw` sur la VM 1 |
| `Vagrantfile` | Déclenche le provisioning Ansible au `vagrant up` |

### Chaîne de déploiement

```
vagrant up cible
    └── ansible_local → ansible/playbook-cible.yml
            └── rôle ufw (après node_exporter et fastapi_app)
                    └── ufw status verbose (vérification)
```

Le rôle `ufw` est exécuté **en 3ᵉ position** dans le playbook, après le déploiement de Node Exporter et de FastAPI, afin que les services existent avant d'activer le pare-feu.

---

## Règles appliquées

Politique par défaut : **deny** sur le trafic **entrant** — tout ce qui n'est pas explicitement autorisé est bloqué.

| # | Règle | Port | Protocole | Source autorisée | Justification |
|---|-------|------|-----------|------------------|---------------|
| 1 | SSH | 22 | tcp | Toutes | Évite de couper l'accès Vagrant/Ansible ; **doit être ajoutée avant d'activer UFW** |
| 2 | Node Exporter | 9100 | tcp | `192.168.56.20` uniquement | Prometheus (VM 2) scrape les métriques système |
| 3 | FastAPI (métriques) | 5000 | tcp | `192.168.56.20` uniquement | Prometheus scrape l'endpoint `/metrics` |
| 4 | FastAPI (navigateur) | 5000 | tcp | Toutes | Accès depuis l'hôte Windows via le port forwardé Vagrant (NAT VirtualBox `10.0.2.2`) |
| — | Politique par défaut | — | — | — | **Bloquer** tout autre trafic entrant |

### Détail des règles sensibles

**SSH (port 22)** — Critique pour le provisioning. Si UFW est activé sans cette règle, Vagrant perd la connexion SSH et la VM devient inaccessible.

**Ports 9100 et 5000 depuis la VM monitoring** — Seule l'IP `monitoring_ip` (définie dans `defaults/main.yml` : `192.168.56.20`) peut joindre ces ports sur le réseau privé VirtualBox. Cela simule une isolation réseau : un tiers sur le réseau `192.168.56.0/24` ne peut pas scraper les métriques.

**Port 5000 ouvert globalement** — Le `forwarded_port` Vagrant pour FastAPI transite par l'interface NAT VirtualBox (`10.0.2.2`), pas par l'IP privée. Une règle restreinte à `192.168.56.20` ne suffirait pas pour l'accès depuis le navigateur Windows sur `http://localhost:5000`.

---

## Fichiers source

### `ansible/roles/ufw/defaults/main.yml`

```yaml
monitoring_ip: "192.168.56.20"
```

### `ansible/playbook-cible.yml`

```yaml
roles:
  - node_exporter
  - fastapi_app
  - ufw             # Pare-feu : seule VM 2 peut scraper :9100 et :5000
  - filebeat
```

---

## Vérification

Sur la VM cible :

```bash
vagrant ssh cible
sudo ufw status verbose
```

Résultat attendu (ordre indicatif) :

- `22/tcp` — ALLOW (Anywhere)
- `9100/tcp` — ALLOW from `192.168.56.20`
- `5000/tcp` — ALLOW from `192.168.56.20`
- `5000/tcp` — ALLOW (Anywhere)
- Default: deny (incoming)

---

## Crash-test réseau (pare-feu)

Pour simuler une panne réseau et observer l'impact sur Prometheus :

```bash
vagrant ssh cible
sudo ufw deny 9100    # Bloquer Node Exporter
# → Prometheus : target node-cible passe DOWN
sudo ufw delete deny 9100   # Rétablir
```

Voir aussi la section « Panne réseau (pare-feu) » dans le `README.md`.

---

## Dépannage

| Symptôme | Cause probable | Action |
|----------|------------------|--------|
| Target DOWN dans Prometheus | UFW bloque le scrape | `sudo ufw status` sur VM 1, vérifier les règles pour `:9100` et `:5000` depuis `192.168.56.20` |
| Impossible de joindre FastAPI depuis Windows | Règle `:5000` manquante ou UFW désactivé | Vérifier `ALLOW 5000/tcp` sans restriction de source |
| Perte d'accès SSH après provisioning | SSH non autorisé avant activation UFW | Depuis la console VirtualBox : `sudo ufw allow 22/tcp` puis `sudo ufw reload` |

---

## Ce qui n'est pas couvert

- **VM 2 (monitoring)** : pas de rôle UFW ; Prometheus, Grafana, ELK écoutent sans filtrage réseau Ansible.
- **Filebeat → Logstash** : le trafic sortant de la VM 1 vers `:5044` sur la VM 2 n'est pas restreint par UFW (politique deny ne s'applique qu'au trafic **entrant** sur la cible).
- **Port 9100 depuis l'hôte** : le forward Vagrant `host:9100 → guest:9100` peut être bloqué si aucune règle n'autorise `:9100` depuis l'extérieur de `192.168.56.20` — comportement voulu pour la démo de sécurité.
