## DOSSIER D'ARCHITECTURE ET D'EXPLOITATION

## Workshop Évalué — Ingénierie de l'Observabilité Sécurisée

M2-Shop — Plateforme de commerce électronique

| Contexte | Valeur |
| --- | --- |
| Référentiel | ANSSI — Guide d'hygiène informatique / Zone Trust Model |
| Environnement | 3 VMs Vagrant + VirtualBox (Debian 12 Bookworm) |
| Zone Production | web-prod — 10.0.20.20 (DMZ Production) |
| Zone Administration | supervision — 10.0.10.5 (DMZ Admin / Supervision) |
| Pare-feu inter-zones | fw-router — 10.0.20.1 / 10.0.10.1 (nftables Zero-Trust) |
| Hyperviseur | VirtualBox + Vagrant + Ansible (ansible_local) |
| Référence sujet | Workshop Évalué M2 — Infrastructure Cloud |
| Date de remise | 01 juillet 2026 — 17h00 |
| Lien github vers le projet | https://github.com/dimitriangely/TP-Mrdecker/tree/main/Wokrshop-final |

| Section 1 | Section 2 | Section 3 | Statut |
| --- | --- | --- | --- |
| Architecture Réseau (DAT) | Dossier d'Exploitation (DEX) | Plan de Continuité (PCO) | 4/4 jalons validés en VM |

Correspondance **Bloc 5** (ce DAE est le livrable principal, pas le seul) :

| Compétence | Dans ce DAE | Fichier complémentaire |
| --- | --- | --- |
| C5.1.1 / C5.1.2 | — | `docs/C5.1.1-C5.1.2-cartographie-et-contraintes.md` |
| C5.1.3 Cahier des charges | § 1 + matrice | `docs/matrice-de-flux.md` |
| C5.2.1 Architecture | § 1.1–1.4 | — |
| C5.2.2 / C5.3.3 Recette | § 1.5 | `docs/tests-de-validation.md` |
| C5.2.3 PoC | preuves § 2.3–2.4 | `docs/demo-jury.md` |
| C5.3.1 / C5.3.2 IaC | méthode `ansible_local` | `docs/C5.3.1-C5.3.2-protocole-integration.md` |
| C5.4.1 Guide | § 2–3 | `docs/C5.4.1-guide-utilisation-sre.md` |
| Index grille | — | `docs/correspondance-grille-bloc5.md` |


## Section 1 — Architecture Réseau (DAT)

*Livrable C5.1.3 (synthèse du cahier des charges) et C5.2.1 (présentation d'architecture).*

Cette section décrit l'architecture réseau de la plateforme d'observabilité sécurisée déployée pour M2- Shop, conformément aux exigences ANSSI du sujet. L'ensemble de l'infrastructure est défini en Infrastructure as Code (IaC) via Vagrant et Ansible, permettant une reconstruction complète en moins de 10 minutes.

## 1.1 Vue d'ensemble de l'architecture

L'infrastructure est organisée en trois zones réseau physiquement cloisonnées, sans aucun réseau privé VirtualBox commun entre la zone Production et la zone Administration. Tout flux inter-zone transite obligatoirement par le pare-feu dédié fw-router.

*Figure 1.1 — Architecture réseau à trois zones cloisonnées (DMZ Production, Pare-feu inter-zones, DMZ Administration)*


## 1.2 Inventaire des composants

| VM | Rôle | IP | Zone | Ressources |
| --- | --- | --- | --- | --- |
| web-prod | Nginx, Node Exporter, Zabbix Agent2, Promtail, Webhook receiver | 10.0.20.20 | DMZ Production | 1 vCPU, 1 Go RAM |
| fw-router | nftables Zero-Trust, routage inter-zones | 10.0.20.1 / 10.0.10.1 | Inter-zones | 1 vCPU, 512 Mo RAM |
| supervision | Prometheus, Alertmanager, Zabbix Server, Loki, Grafana | 10.0.10.5 | DMZ Administration | 2 vCPU, 2 Go RAM |

*Tableau 1.1 — Inventaire des machines virtuelles*

## 1.3 Routage statique inter-zones

Le cloisonnement physique (deux réseaux VirtualBox `intnet` disjoints, aucun réseau privé commun entre web-prod et supervision) ne suffit pas à garantir que les paquets inter-zones traversent fw-router. Chaque VM n'a d'adresse que sur **son** `/24`. fw-router n'est **pas** la passerelle par défaut : la route par défaut de chaque machine pointe vers le NAT VirtualBox (`eth0`). Sans route plus spécifique, un paquet à destination de l'autre zone sort vers Internet/NAT. La chaîne FORWARD de nftables n'est alors jamais sollicitée, et le Zero-Trust se réduit à un timeout silencieux, sans preuve d'audit.

Deux routes statiques persistantes (unités systemd déployées par Ansible) forcent le next-hop inter-zones via la patte correspondante de fw-router :

| Hôte | Destination | Next-hop | Interface | Unité systemd |
| --- | --- | --- | --- | --- |
| web-prod (10.0.20.20) | 10.0.10.0/24 (DMZ Admin) | 10.0.20.1 | eth1 | static-route-admin.service |
| supervision (10.0.10.5) | 10.0.20.0/24 (DMZ Prod) | 10.0.10.1 | eth1 | static-route-prod.service |

*Tableau 1.2 — Routes statiques inter-zones (préalable indispensable au filtrage FORWARD)*

Sans ces routes, la matrice de flux (tableau 1.3) et les règles nftables de fw-router restent une intention : aucun paquet n'atteint le pare-feu inter-zones. Le routage et le filtrage forment ensemble le Jalon A. Validation : `ip route show 10.0.10.0/24` sur web-prod doit afficher `via 10.0.20.1 dev eth1` (symétrique sur supervision).

## 1.4 Matrice de flux réglementaire

La politique par défaut est DROP sur toutes les chaînes nftables (FORWARD du routeur **et** INPUT/OUTPUT de chaque hôte). Deux plans distincts doivent être lus séparément. Les mélanger ferait croire, à tort, que le site public Nginx ou SSH transitent par fw-router.

1. **Plan inter-zones (FORWARD fw-router)** — seuls ces flux traversent le pare-feu entre DMZ Prod et DMZ Admin.
2. **Plan hôte (INPUT/OUTPUT locaux)** — administration, diagnostic, mises à jour, site public et accès Grafana. Ces flux sont acceptés **sur la VM concernée** (souvent via `eth0` NAT VirtualBox). Ils **ne passent pas** par la chaîne FORWARD de fw-router.

### 1.4.1 Plan inter-zones (FORWARD fw-router)

| Zone source | IP source | Zone dest. | IP dest. | Proto | Port | Chiffrement | Justification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DMZ Admin | 10.0.10.5 | DMZ Prod | 10.0.20.20 | TCP | 9100 | TLS v1.3 + Basic Auth bcrypt | Scraping Prometheus (PULL) |
| DMZ Prod | 10.0.20.20 | DMZ Admin | 10.0.10.5 | TCP | 10051 | TLS-PSK 64 hex | Zabbix Agent2 mode PUSH (actif strict) |
| DMZ Prod | 10.0.20.20 | DMZ Admin | 10.0.10.5 | TCP | 3100 | HTTP (réseau isolé) | Promtail → Loki (logs Nginx) |
| DMZ Admin | 10.0.10.5 | DMZ Prod | 10.0.20.20 | TCP | 9095 | **HTTP en clair** | Alertmanager → webhook `/alert` (auto-healing) |

*Tableau 1.3 — Flux FORWARD inter-zones uniquement (fw-router)*

**Écart de durcissement assumé (Jalon D) :** le webhook d'auto-healing écoute `http://10.0.20.20:9095/alert`. Contrairement aux collecteurs 9100 (TLS v1.3) et 10051 (PSK), ce flux n'est pas chiffré. Le risque est limité au labo (réseau `intnet` non routé vers Internet, payload restreint à l'alerte `NginxDown` / `firing`, script sudoers chirurgical). En production réelle, ce canal devrait être passé en HTTPS mutuel ou remplacé par un bus interne authentifié.

### 1.4.2 Plan hôte (INPUT / OUTPUT nftables locaux)

Ces règles apparaissent dans `nft list ruleset` sur chaque VM. Elles sont déclarées ici pour qu'un audit DAT / nftables ne trouve aucun flux « fantôme ».

| Plan | Source | Destination | Proto | Port | Chaîne (hôte) | Justification |
| --- | --- | --- | --- | --- | --- | --- |
| Admin local | Hôte SRE / Vagrant (NAT `eth0`) | web-prod, fw-router, supervision | TCP | 22 | INPUT des 3 VMs | SSH d'administration du labo. **Non autorisé en FORWARD** : un SSH inter-zones (ex. web-prod → supervision:22) timeout. |
| Diagnostic | Any (destiné à l'hôte lui-même) | VM locale | ICMP | echo-request | INPUT des 3 VMs | Ping de diagnostic. ICMP n'est **pas** autorisé en FORWARD inter-zones. |
| Résolution | VM locale | Internet (NAT) | UDP/TCP | 53 | OUTPUT web-prod, fw-router, supervision | DNS indispensable aux dépôts APT / GitHub. |
| Mises à jour | web-prod, fw-router | Internet (NAT) | TCP | 80 / 443 | OUTPUT de ces hôtes | Téléchargement de paquets (Node Exporter, Zabbix, etc.). |
| Alerting sortant | supervision (10.0.10.5) | Internet | TCP | 443 | OUTPUT supervision | Webhook Slack unique (`#alertes-m2shop`). |
| Site public | Internet / client | web-prod (10.0.20.20) | TCP | 80 / 443 | **INPUT web-prod uniquement** | Nginx fil rouge (HTTP → HTTPS). **Absent de FORWARD fw-router** : le public arrive sur `eth1`/`eth0` de web-prod, pas via le routeur inter-zones. |
| Dashboard SRE | Hôte Windows (SRE) | supervision | TCP | 3000 (invité) | INPUT supervision | Grafana en **HTTPS dans la VM** (`grafana.ini` : `protocol = https`, port 3000). Depuis Windows : port-forward Vagrant `127.0.0.1:3443` → `10.0.10.5:3000`. URL d'accès hôte : `https://127.0.0.1:3443`. |

*Tableau 1.4 — Flux hôte (hors FORWARD inter-zones)*

Règles explicitement interdites (plan FORWARD) : aucun flux initié depuis la zone Admin vers la zone Prod en dehors des ports 9100 et 9095 ; aucun flux initié par le serveur Zabbix vers l'agent (mode Push strict) ; connexion directe web-prod ↔ supervision physiquement impossible (pas de réseau privé commun) ; SSH 22, ICMP, DNS et HTTP(S) public **ne traversent pas** fw-router.

Défense en profondeur (Zone Trust Model ANSSI) : fw-router n'est pas le seul point de contrôle. Sur supervision, les collecteurs 10051 (Zabbix) et 3100 (Loki) n'acceptent **que** l'IP `10.0.20.20`. Même si le pare-feu inter-zones était contourné ou mal configuré, un hôte tiers de la zone Admin ne pourrait pas pousser de données vers Zabbix Server ou Loki. Le détail des règles figure au § 2.1.3.

## 1.5 Résultats de validation — Protocole de recette (Jalons A à D)

| Test | Résultat attendu | Résultat observé |
| --- | --- | --- |
| Route statique web-prod → 10.0.10.0/24 | via 10.0.20.1 dev eth1 | Route présente et persistante (systemd) |
| Route statique supervision → 10.0.20.0/24 | via 10.0.10.1 dev eth1 | Route présente et persistante (systemd) |
| Port 22 depuis web-prod → supervision | TIMEOUT (DROP) | TIMEOUT OK — Zero-Trust validé |
| Port 10051 depuis web-prod → supervision (sans service) | Connection refused (RST) | Connection refused — paquet traverse fw-router |
| Port 9100 : curl -k sans credentials 401 Unauthorized |   | 401 reçu — Basic Auth opérationnel |
| TLS version négociée sur Node Exporter | TLSv1.3 uniquement | TLSv1.3 + TLS_AES_128_GCM_SHA256 |
| Prometheus target health | health: up | health=up, lastError vide |
| Capture tcpdump flux Zabbix PSK sur port 10051 | Payload chiffré illisible | Payload binaire chiffré, identité PSK visible en clair (normal) |
| Crash Test Nginx + auto-healing | Nginx relancé < 60s, alerte Slack | 5 secondes (firing 19:25:29 → relancé 19:25:34) |

*Tableau 1.5 — Résultats du protocole de recette technique*


## Section 2 — Dossier d'Exploitation (DEX)

Cette section rassemble les configurations techniques déployées, les preuves de chiffrement collectées lors des validations, et les incidents rencontrés et résolus au cours du déploiement.

## 2.1 Configuration des règles de filtrage

## 2.1.1 fw-router — Pare-feu inter-zones (nftables Zero-Trust)

Configuration déployée via Ansible (roles/fw-router/templates/nftables-router.conf.j2). Politique par défaut : DROP sur toutes les chaînes. Seuls les flux du plan inter-zones (tableau 1.3) passent en FORWARD. Les flux du tableau 1.4 (SSH, ICMP, DNS, HTTP(S) public, Grafana) sont traités sur les chaînes INPUT/OUTPUT des hôtes, jamais par fw-router.

```
\# fw-router — nftables Zero-Trust (extrait des règles FORWARD)
define IF_PROD = "eth1" # 10.0.20.1 <-> web-prod (10.0.20.20)
define IF_ADMIN = "eth2" # 10.0.10.1 <-> supervision (10.0.10.5)
chain forward {
type filter hook forward priority 0; policy drop;
ct state established,related accept
# Prometheus scraping (PULL) : Admin → Prod, port 9100
iifname $IF_ADMIN oifname $IF_PROD \
ip saddr 10.0.10.5 ip daddr 10.0.20.20 tcp dport 9100 ct state new accept
# Zabbix Agent Push : Prod → Admin, port 10051
iifname $IF_PROD oifname $IF_ADMIN \
ip saddr 10.0.20.20 ip daddr 10.0.10.5 tcp dport 10051 ct state new accept
# Promtail → Loki : Prod → Admin, port 3100
iifname $IF_PROD oifname $IF_ADMIN \
ip saddr 10.0.20.20 ip daddr 10.0.10.5 tcp dport 3100 ct state new accept
# Alertmanager → Webhook auto-healing : Admin → Prod, port 9095
iifname $IF_ADMIN oifname $IF_PROD \
ip saddr 10.0.10.5 ip daddr 10.0.20.20 tcp dport 9095 ct state new accept
log prefix "NFT-FORWARD-DROP: " counter drop
}
```

## 2.1.2 web-prod — Défense en profondeur (nftables hôte, Jalon A)

Configuration hôte complémentaire au pare-feu inter-zones (`roles/web-prod/templates/nftables-webprod.conf.j2`). Restreint les flux au niveau de la machine elle-même, en cohérence avec les tableaux 1.3 (inter-zones) et 1.4 (plan hôte). L'OUTPUT n'est pas limité à Zabbix/Promtail : DNS, HTTP/HTTPS sortants et ICMP sont nécessaires aux mises à jour et au diagnostic. La chaîne FORWARD est DROP (web-prod n'est pas un routeur).

```
# web-prod — nftables hôte (INPUT / OUTPUT / FORWARD)
chain input {
    type filter hook input priority 0; policy drop;
    iif "lo" accept
    ct state established,related accept
    tcp dport { 80, 443 } ct state new accept          # Nginx public (plan hôte)
    ip saddr 10.0.10.5 tcp dport 9100 ct state new accept  # Prometheus scraping
    ip saddr 10.0.10.5 tcp dport 9095 ct state new accept  # Webhook auto-healing
    tcp dport 22 ct state new accept                  # SSH admin (pas de FORWARD)
    ip protocol icmp icmp type echo-request accept    # ping local
    log prefix "NFT-WEBPROD-INPUT-DROP: " counter drop
}
chain output {
    type filter hook output priority 0; policy drop;
    oif "lo" accept
    ct state established,related accept
    udp dport 53 accept                               # DNS (APT / GitHub)
    tcp dport 53 accept
    ip daddr 10.0.10.5 tcp dport 10051 ct state new accept  # Zabbix Push
    ip daddr 10.0.10.5 tcp dport 3100 ct state new accept   # Promtail → Loki
    tcp dport 443 accept                              # mises à jour HTTPS
    tcp dport 80 accept                               # mises à jour HTTP
    ip protocol icmp accept                           # réponses / diagnostic
    log prefix "NFT-WEBPROD-OUTPUT-DROP: " counter drop
}
chain forward {
    type filter hook forward priority 0; policy drop; # pas de routage sur web-prod
}
```

## 2.1.3 supervision — Défense en profondeur (nftables hôte, argument ANSSI)

Configuration déployée via `roles/supervision/templates/nftables-supervision.conf.j2`. C'est le pendant admin de § 2.1.2, et l'argument de durcissement le plus fort du DAT au regard du *Guide d'hygiène informatique* / Zone Trust Model : **un collecteur n'accepte que la source métier légitime, pas « tout ce qui a traversé le routeur »**.

fw-router filtre déjà les ports 10051 et 3100 en FORWARD. Si l'on s'arrêtait là, une compromission du routeur, une règle FORWARD trop large, ou un second hôte branché sur `net-admin` suffirait à parler à Zabbix Server et à Loki. Les règles INPUT de supervision ferment cette porte :

- `tcp dport 10051` : `ip saddr 10.0.20.20` uniquement (push Zabbix Agent2).
- `tcp dport 3100` : `ip saddr 10.0.20.20` uniquement (Promtail → Loki).

Symétriquement, l'OUTPUT n'autorise le scraping et l'auto-healing **que** vers cette même IP (`daddr 10.0.20.20` ports 9100 et 9095). La zone Admin ne peut pas initier un flux métier vers un autre hôte de production. FORWARD est DROP : supervision n'est pas un pont vers la DMZ Prod.

Grafana (3000/TCP, HTTPS) reste ouvert en INPUT sans restriction d'IP source : c'est l'accès SRE du labo (et le port-forward Vagrant `127.0.0.1:3443`). En production réelle, ce port serait limité à un bastion.

```
# supervision — nftables hôte (INPUT / OUTPUT / FORWARD)
chain input {
    type filter hook input priority 0; policy drop;
    iif "lo" accept
    ct state established,related accept
    ip saddr 10.0.20.20 tcp dport 10051 ct state new accept  # Zabbix : UNIQUEMENT web-prod
    tcp dport 3000 ct state new accept                       # Grafana HTTPS (accès SRE)
    ip saddr 10.0.20.20 tcp dport 3100 ct state new accept   # Loki : UNIQUEMENT web-prod
    tcp dport 22 ct state new accept                         # SSH admin (pas de FORWARD)
    ip protocol icmp icmp type echo-request accept
    log prefix "NFT-SUPERVISION-INPUT-DROP: " counter drop
}
chain output {
    type filter hook output priority 0; policy drop;
    oif "lo" accept
    ct state established,related accept
    udp dport 53 accept
    tcp dport 53 accept
    ip daddr 10.0.20.20 tcp dport 9100 accept   # Prometheus → Node Exporter uniquement
    ip daddr 10.0.20.20 tcp dport 9095 accept   # Alertmanager → webhook uniquement
    tcp dport 443 accept                        # Slack sortant
    ip protocol icmp accept
    log prefix "NFT-SUPERVISION-OUTPUT-DROP: " counter drop
}
chain forward {
    type filter hook forward priority 0; policy drop;
}
```


## 2.2 Code source commenté du script de remédiation automatique

Déployé à /usr/local/bin/restart-nginx.sh, exécuté par le compte non-root healer via la règle sudoers chirurgicale. Le script est délibérément minimal pour réduire la surface d'attaque.

```
#!/bin/bash
# restart-nginx.sh — conforme à roles/web-prod/templates/restart-nginx.sh.j2
# Exécuté par le compte non-root "healer" via sudo restreint.
# Ne fait qu'une chose : relancer Nginx et journaliser l'action.
set -euo pipefail
LOG_FILE="/var/log/healer/remediation.log"
TIMESTAMP=$(date -u "+%Y-%m-%dT%H:%M:%SZ")
echo "[${TIMESTAMP}] Déclenchement de la remédiation automatique : relance de nginx.service" >> "${LOG_FILE}"
# sudo -n : mode non-interactif — échoue immédiatement si le mot de passe
# est requis (impossible sous systemd sans TTY) plutôt que de bloquer.
# La règle sudoers autorise UNIQUEMENT cette commande exacte.
if sudo -n /usr/bin/systemctl restart nginx.service; then
    echo "[${TIMESTAMP}] Remédiation réussie : nginx.service relancé" >> "${LOG_FILE}"
    exit 0
else
    echo "[${TIMESTAMP}] ÉCHEC de la remédiation : nginx.service n'a pas pu être relancé" >> "${LOG_FILE}"
    exit 1
fi
```

Règle sudoers chirurgicale (/etc/sudoers.d/supervision) : healer ALL=(root) NOPASSWD: /usr/bin/systemctl restart nginx.service Une seule ligne, une seule commande exacte, sans wildcard. Le compte healer ne peut rien faire d'autre en mode élevé. Le fichier est validé par visudo -cf avant déploiement (Ansible refuse un sudoers syntaxiquement incorrect).

## 2.3 Preuves de chiffrement

## 2.3.1 Node Exporter — TLS v1.3 + Basic Auth

Commande exécutée sur web-prod :

```
echo | openssl s_client -connect localhost:9100 -tls1_3 2>&1 | grep -E 'Protocol|Cipher'
```

Résultat observé en VM (protocole de recette) :

```
New, TLSv1.3, Cipher is TLS_AES_128_GCM_SHA256
    Protocol  : TLSv1.3
    Cipher    : TLS_AES_128_GCM_SHA256
```

Sans credentials : `curl -k https://localhost:9100/metrics` → **401** (Basic Auth bcrypt opérationnel). Les captures d'écran d'origine sont à réinsérer dans le PDF de remise (perdues à l'export Markdown).

## 2.3.2 Zabbix PSK — Capture tcpdump sur fw-router (port 10051)

Capture réalisée sur l'interface eth2 du fw-router pendant un cycle de heartbeat Zabbix Agent2 → Zabbix Server :

```
vagrant ssh fw-router -c "sudo timeout 20 tcpdump -i eth2 port 10051 -nn -X"
```

Résultat observé : handshakes TLS-PSK répétés réussis ; identité `PSK_WEBPROD_001` visible en clair dans le ClientHello ; payload applicatif binaire illisible. Ce comportement est normal (RFC 4279) : l'identité PSK n'est pas un secret, elle indique au serveur quelle clé utiliser. Joindre la capture (ou un extrait hex) en annexe du PDF.

## 2.3.3 Webhook auto-healing (HTTP) et accès Grafana

Le récepteur d'auto-healing (`/usr/local/bin/webhook-receiver.py`) écoute en HTTP clair sur `0.0.0.0:9095`, chemin `POST /alert`. Alertmanager l'appelle via `http://10.0.20.20:9095/alert`. Ce choix est volontairement documenté comme exception au chiffrement des collecteurs (voir § 1.4.1) : surface limitée au labo, pas de TLS côté webhook dans l'état actuel du playbook.

Grafana est servi en HTTPS uniquement **à l'intérieur** de la VM supervision (port 3000, certificat auto-signé). L'accès depuis l'hôte Windows n'est pas un flux FORWARD : Vagrant publie `127.0.0.1:3443` vers `guest:3000`. URL SRE : `https://127.0.0.1:3443`.

## 2.4 Validation du Crash Test & Auto-Healing (Jalon D)

Protocole de recette exact exécuté le 30 juin 2026. Déclenchement : `sudo systemctl stop nginx` sur web-prod. Les deux premiers essais ont été une reprise **manuelle** ; les deux derniers valident la chaîne automatique (Prometheus → Alertmanager → Slack + webhook → `healer`).

| Horodatage (UTC) | Événement | Preuve |
| --- | --- | --- |
| 19:25:29 | `nginx.service` arrêté ; alerte `NginxDown` **firing** | Alertmanager + message Slack `#alertes-m2shop` |
| 19:25:29 | Webhook `POST /alert` reçu sur web-prod:9095 | `/var/log/healer/webhook-receiver.log` |
| 19:25:34 | Script `restart-nginx.sh` : remédiation réussie | `/var/log/healer/remediation.log` |
| 19:25:34 | `nginx.service` de nouveau **active** | `systemctl is-active nginx` |
| ~19:25:34 | Alerte **resolved** publiée sur Slack (`send_resolved: true`) | Canal `#alertes-m2shop` |

*Tableau 2.1 — Chronologie du Crash Test Auto-Healing (30 juin 2026)*

Délai total firing → relance : **5 secondes** (exigence sujet : < 60 s). Le webhook Alertmanager a `send_resolved: false` pour ne pas relancer Nginx à la résolution.

## 2.5 Incidents rencontrés et résolus

Les incidents suivants ont été rencontrés lors du déploiement. Leur résolution est documentée ici car elle illustre la maîtrise réelle de l'environnement et constitue une valeur ajoutée pour le DEX.

|   | # Incident | Cause identifiée | Résolution |
| --- | --- | --- | --- |
|   | 1 URL du paquet zabbix-release : HTTP 404 | Chemin /release/ en trop dans l'URL construite à partir de la documentation | Vérification de l'URL réelle sur repo.zabbix.com — correction du template Ansible |
|   | 2 Zabbix TLS-PSK : handshake failure intermittent (no suitable signature algorithm) | Bug OpenSSL 3.0.x sur Debian 12 dans la négociation TLS 1.3 pour les cipher suites PSK pures | Mise à jour **manuelle** de openssl/libssl3 + redémarrage zabbix-agent2 / zabbix-server. **Pas dans Ansible** : un `vagrant up` neuf peut reproduire le bug tant que les paquets distants n'ont pas ce correctif. |
|   | 3 Zabbix : hostid=0 en base (host not found) | Le schéma Zabbix n'utilise pas l'auto-increment MySQL — INSERT sans hostid explicite génère hostid=0 | Script SQL corrigé avec MAX(hostid)+1 et mise à jour de la table ids interne de Zabbix |
|   | 4 Grafana 13 : boucle de redémarrage infinie (Datasource provisioning error) | uid: Loki / uid: Prometheus entrent en conflit avec la résolution interne du nouveau système de provisioning de Grafana 13 | UID distincts : prometheus_ds, loki_ds — suppression de la base SQLite corrompue (rm grafana.db) |
|   | 5 Webhook receiver : permission denied sur le script Python | Fichier déployé en root:root mode 750 — utilisateur healer non membre du groupe root | Changement du groupe propriétaire en root:healer — healer peut lire/exécuter le fichier |

*Tableau 2.2 — Incidents rencontrés et résolus lors du déploiement*


## Section 3 — Plan de Continuité Opérationnelle

## 3.1 Procédure d'Isolation d'Urgence d'un Serveur Web Compromis

Cette procédure s'applique lorsqu'un indicateur de compromission (IOC) est détecté sur le serveur web de production web-prod (10.0.20.20). Elle vise à confiner l'incident en moins de 10 minutes, limiter la propagation latérale, et préserver les éléments de preuve nécessaires à l'investigation forensique ultérieure.

Elle **respecte la matrice de flux** (tableaux 1.3 et 1.4). Aucune étape ne suppose un flux FORWARD inexistant (HTTPS Admin→Prod, SSH inter-zones, SCP Prod→Admin).

IMPORTANT : Seul un membre de l'équipe SRE/SOC habilité peut exécuter cette procédure. Toute action doit être horodatée et consignée dans le rapport post-mortem correspondant.

## Prérequis

Accès **depuis l'hôte Windows** (plan hôte / NAT VirtualBox `eth0`, jamais via fw-router) :

- `vagrant ssh fw-router` — noms internes `/etc/hosts` : `fw-router-prod` (10.0.20.1) et `fw-router-admin` (10.0.10.1). Le hostname `fw-router` n'existe pas.
- `vagrant ssh web-prod` — SSH vers 10.0.20.20:22 **uniquement** depuis l'hôte (INPUT locale). Un SSH depuis supervision timeout (DROP FORWARD).
- `vagrant ssh supervision`
- Grafana depuis Windows : `https://127.0.0.1:3443` (port-forward Vagrant → guest 3000 HTTPS). Depuis un shell déjà ouvert sur supervision : `https://127.0.0.1:3000`.
- Alertmanager : **uniquement** sur supervision, `http://127.0.0.1:9093`. Le port 9093 n'est pas ouvert en INPUT distante.
- Droits sudo sur fw-router, web-prod et supervision

## Phase 1 — Détection et confirmation (Objectif : < 2 min)

Ne pas tester Nginx par `curl https://10.0.20.20/` depuis la zone Admin : le port 443 Admin→Prod n'est **pas** autorisé en FORWARD (tableau 1.3). Ce curl timeout et ne prouve rien sur l'état du service.

- 1. Vérifier l'alerte dans Grafana (`https://127.0.0.1:3443`) ou sur le canal Slack **`#alertes-m2shop`** (receiver Alertmanager, pas `#monitoring`). Identifier la nature de l'IOC (comportement réseau anormal, pic CPU/mémoire, processus inconnus, logs Nginx suspects).

- 2. Confirmer l'état de Nginx **via Prometheus** (flux 9100 déjà autorisé), depuis supervision :

```
vagrant ssh supervision
curl -s 'http://127.0.0.1:9090/api/v1/query?query=node_systemd_unit_state{name="nginx.service",state="active",instance="10.0.20.20:9100"}'
```

Valeur `1` = service actif côté collecteur ; `0` ou target `down` = indisponibilité ou perte du scrape.

- 3. Consulter les logs Nginx dans Grafana (datasource Loki, jobs `nginx_access` / `nginx_error`) pour identifier les tentatives d'exploitation. Loki a déjà reçu ces logs via Promtail (port 3100, initié par web-prod).

- 4. Décision d'isolation : si le doute persiste, principe de précaution → Phase 2.

## Phase 2 — Confinement réseau d'urgence (Objectif : < 5 min)

IRRÉVERSIBLE : les règles ci-dessous coupent **tous** les flux FORWARD vers/depuis web-prod (9100, 10051, 3100, 9095). Le serveur devient invisible de la zone Admin. L'impact client est immédiat si l'attaquant utilisait un relais inter-zones ; le site public (INPUT web-prod 80/443, hors FORWARD) n'est coupé qu'à l'étape d'isolation locale.

Connexion au routeur depuis l'hôte :

```
vagrant ssh fw-router
```

Insertion d'un DROP total en tête de FORWARD (table `inet filter`, déjà déployée par Ansible) :

```
sudo nft insert rule inet filter forward ip saddr 10.0.20.20 counter drop
sudo nft insert rule inet filter forward ip daddr 10.0.20.20 counter drop
sudo nft list chain inet filter forward
```

Les compteurs doivent s'incrémenter. Prometheus passera `down`, Zabbix/Promtail cesseront de traverser.

Isolation locale renforcée (double boucle), **uniquement** via l'hôte — pas depuis 10.0.10.0/24 :

```
vagrant ssh web-prod
sudo nft flush ruleset
sudo nft add table inet filter
sudo nft add chain inet filter input '{ type filter hook input priority 0 ; policy drop ; }'
sudo nft add chain inet filter output '{ type filter hook output priority 0 ; policy drop ; }'
sudo nft add chain inet filter forward '{ type filter hook forward priority 0 ; policy drop ; }'
sudo nft add rule inet filter input iif "lo" accept
sudo nft add rule inet filter input ct state established,related accept
# SSH labo depuis l'hôte (NAT eth0) — PAS depuis la DMZ Admin
sudo nft add rule inet filter input tcp dport 22 accept
```

Conserver le port 22 en INPUT sans le restreindre à `10.0.10.0/24` : ce réseau n'a jamais le droit de joindre web-prod:22 à travers fw-router. Couper 22 ferait perdre `vagrant ssh` (seul accès restant hors console VirtualBox).

## Phase 3 — Préservation des preuves (Objectif : < 8 min)

Le SCP web-prod → supervision:22 est **interdit** par la matrice (pas de FORWARD 22, pas d'OUTPUT 22 sur web-prod). Les artefacts sortent vers l'hôte via le dossier partagé `/vagrant` (projet Windows).

- 5. Depuis fw-router, capturer le trafic restant sur la patte Prod :

```
vagrant ssh fw-router -c "sudo tcpdump -i eth1 host 10.0.20.20 -w /vagrant/capture-incident-\$(date +%Y%m%d-%H%M%S).pcap"
```

(adapter `eth1` si `ip a` montre `enp0s8` / `enp0s9`.)

- 6. Depuis web-prod, archiver les logs **vers `/vagrant`** :

```
vagrant ssh web-prod -c "sudo tar czf /vagrant/logs-incident-\$(date +%Y%m%d-%H%M%S).tar.gz /var/log/nginx/ /var/log/zabbix/ /var/log/healer/ /var/log/auth.log"
```

- 7. Image mémoire vive minimale (processus + sockets) :

```
vagrant ssh web-prod -c "sudo ps auxf > /vagrant/processes-\$(date +%Y%m%d-%H%M%S).txt"
vagrant ssh web-prod -c "sudo ss -tulpn > /vagrant/netstat-\$(date +%Y%m%d-%H%M%S).txt"
```

- 8. Contrôler côté hôte Windows que les fichiers sont bien dans le répertoire du projet (montage `/vagrant`). Ne pas tenter `scp` vers 10.0.10.5.

## Phase 4 — Notification et escalade (Objectif : < 10 min)

- 9. Ouvrir un ticket d'incident : heure de détection, IOC, actions déjà effectuées, impacts (site public, perte de supervision inter-zones).

- 10. Notifier le responsable sécurité et la hiérarchie directe.

- 11. Silencer Alertmanager **depuis supervision**, vers localhost (9093 n'écoute pas à distance) :

```
vagrant ssh supervision -c "amtool --alertmanager.url=http://127.0.0.1:9093 silence add alertname=NginxDown --comment='Incident en cours - isolement volontaire' --duration=4h"
```

- 12. Conserver cette procédure ouverte et horodater chaque action dans le post-mortem.

| Phase | Objectif | Action clé | Délai cible |
| --- | --- | --- | --- |
| 1 — Détection | Confirmer l'IOC | Slack `#alertes-m2shop` + Grafana + requête Prometheus `nginx.service` | < 2 min |
| 2 — Confinement | Couper les flux inter-zones | `nft insert` DROP saddr/daddr 10.0.20.20 sur fw-router ; isolation locale via `vagrant ssh web-prod` | < 5 min |
| 3 — Préservation | Protéger les preuves | tcpdump fw-router + archives vers `/vagrant` (pas de SCP inter-zones) | < 8 min |
| 4 — Escalade | Notifier | Ticket + `amtool` sur `127.0.0.1:9093` | < 10 min |

*Tableau 3.1 — Synthèse des phases d'isolation d'urgence avec délais cibles*

## Rétablissement du service

Le rétablissement n'est effectué qu'après analyse complète des preuves et confirmation que le serveur est sain (ou après substitution par une nouvelle instance reconstruite depuis l'IaC).

- Reconstruction depuis le `Vagrantfile` + Ansible (`vagrant destroy web-prod && vagrant up web-prod` si l'hôte est considéré brûlé). RTO visé en TP : reconstruction IaC.
- Sur fw-router : supprimer les deux règles `insert` DROP (`nft delete rule inet filter forward handle <n>` après `nft -a list chain inet filter forward`), **seulement** une fois web-prod ressourcé et ses nftables Ansible rejouées.
- Rejouer les tests de validation des Jalons A, B, C, D (`docs/tests-de-validation.md`) avant remise en service.
- Lever le silence : `amtool --alertmanager.url=http://127.0.0.1:9093 silence expire <id>` depuis supervision.
- Confirmer Grafana (`https://127.0.0.1:3443`) : target Prometheus `up`, labels Loki présents, plus d'alerte `NginxDown` firing.

## 3.2 Sauvegardes et limites du PRA (PoC)

Il n'existe **pas** de politique de backup planifiée (pas de `mysqldump` Zabbix/MariaDB, pas de snapshot `grafana.db`, pas de rétention Loki hors disque VM, pas de cron).

| Donnée | En production on sauvegarderait | Dans ce PoC |
| --- | --- | --- |
| Config SI | Git + playbooks | **Git / IaC** = seule « sauvegarde » de l'état voulu |
| Base Zabbix | Dump MariaDB chiffré, hors site | Perdue si la VM supervision est détruite ; hôte réenregistré au `vagrant provision` |
| Grafana | `grafana.db` + provisioning | Le provisioning Ansible recrée datasources/dashboard ; l'historique UI non |
| Logs Loki / Nginx | Packer / rétention distante | Locaux ; archive **forensique** uniquement (PCO phase 3 → `/vagrant`) |
| Secrets | Vault d'entreprise | Vault Ansible de labo, mot de passe sur les VMs |

**PRA du PoC = reconstruction IaC**, pas une restauration. C'est une contrainte pédagogique assumée (C5.1.2), pas un oubli : le sujet valide le cloisonnement et la recette, pas un plan de sauvegarde d'entreprise. En industrialisation : dumps quotidiens MariaDB, export Grafana, rétention Loki, secret manager, et tests de restore.