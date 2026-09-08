# Matrice de Flux Réglementaire — TP Observabilité Sécurisée

**C5.1.3** — synthèse technique du cahier des charges (flux autorisés / interdits).  
**C5.2.1** — contrainte d'architecture (Zero-Trust). Alimente le DAE § 1.4.

Deux plans : **FORWARD inter-zones** (fw-router uniquement) et **INPUT/OUTPUT hôte** (SSH, ICMP, DNS, site public, Grafana). Ne pas les fusionner : Nginx 80/443 et SSH 22 n'apparaissent pas dans la chaîne FORWARD.

## Plan inter-zones (FORWARD fw-router)

| Zone Source  | IP Source    | Zone Dest.    | IP Dest.     | Protocole | Port  | Chiffrement | Justification                          |
|---------------|--------------|----------------|--------------|-----------|-------|-------------|----------------|
| DMZ Admin     | 10.0.10.5    | DMZ Prod       | 10.0.20.20   | TCP       | 9100  | TLS v1.3 + Basic Auth | Scraping Prometheus (PULL) |
| DMZ Prod      | 10.0.20.20   | DMZ Admin      | 10.0.10.5    | TCP       | 10051 | TLS-PSK 64 hex | Zabbix Agent mode Actif (Push) |
| DMZ Prod      | 10.0.20.20   | DMZ Admin      | 10.0.10.5    | TCP       | 3100  | HTTP (réseau isolé) | Promtail -> Loki, logs Nginx |
| DMZ Admin     | 10.0.10.5    | DMZ Prod       | 10.0.20.20   | TCP       | 9095  | **HTTP en clair** | Alertmanager -> webhook `/alert` (auto-healing) |

## Plan hôte (INPUT / OUTPUT locaux, hors FORWARD)

| Source | Destination | Proto | Port | Chaîne | Justification |
|--------|-------------|-------|------|--------|----------------|
| Hôte SRE / Vagrant (NAT eth0) | les 3 VMs | TCP | 22 | INPUT web-prod, fw-router, supervision | SSH labo. Interdit en FORWARD (timeout inter-zones). |
| Any (destiné à l'hôte) | VM locale | ICMP | echo | INPUT des 3 VMs | Diagnostic. Pas de FORWARD ICMP. |
| VM locale | Internet (NAT) | UDP/TCP | 53 | OUTPUT des 3 VMs | DNS (APT / GitHub). |
| web-prod, fw-router | Internet (NAT) | TCP | 80/443 | OUTPUT | Mises à jour paquets. |
| supervision | Internet | TCP | 443 | OUTPUT supervision | Webhook Slack `#alertes-m2shop`. |
| Internet / client | web-prod 10.0.20.20 | TCP | 80/443 | **INPUT web-prod uniquement** | Nginx public. Absent de FORWARD fw-router. |
| Hôte Windows SRE | supervision | TCP | 3000 (invité) | INPUT supervision | Grafana HTTPS dans la VM ; depuis Windows : `127.0.0.1:3443` → guest 3000. |

## Règles explicitement interdites (et vérifiées au protocole de recette)

- Aucun flux FORWARD initié depuis DMZ Admin vers DMZ Prod en dehors des ports 9100/TCP et 9095/TCP.
- Aucun flux initié par le serveur Zabbix (Admin) vers l'agent (Prod) : le mode Push est strict, l'agent initie toujours.
- Toute tentative de connexion directe web-prod <-> supervision en dehors de fw-router est physiquement impossible (pas de réseau privé commun, cf. Vagrantfile).
- Toute tentative depuis web-prod vers supervision sur un port autre que 10051 et 3100 doit expirer (timeout).
- SSH 22, ICMP, DNS et le site public Nginx ne traversent pas fw-router.

## Statut d'implémentation (mis à jour au fil des sessions)

- [x] Nginx (fil rouge) déployé sur web-prod : HTTPS public (TLS auto-signé), redirection HTTP->HTTPS, logs standards access/error.log prêts pour Promtail (validé en VM : 200 en HTTPS, logs présents)
- [x] Promtail (web-prod) -> Loki (supervision) : validé en VM (targets ready, labels nginx_access/nginx_error confirmés côté Loki)
- [x] Grafana (supervision) avec datasources Prometheus + Loki provisionnées automatiquement : validé en VM (service actif, /api/health = 200)
- [x] Grafana en HTTPS only (certificat auto-signé dédié) — validé en VM : service stable, /api/health = 200 en HTTPS
- [x] Dashboard unifié M2-Shop (req/s, taux erreurs 4xx/5xx, CPU, mémoire, logs bruts) provisionné automatiquement — validé en VM
- [x] Jalon D — Alerte NginxDown (Prometheus + Alertmanager + Slack) — validée en VM : déclenchement quasi instantané (<1s entre l'arrêt du service et le déclenchement de l'alerte), message Slack reçu avec heure/hôte/impact conformes au sujet
- [x] Jalon D — Script d'auto-healing + sudoers chirurgical non-root — validé en VM, protocole de recette complet : coupure Nginx -> alerte firing (19:25:29) -> webhook -> script exécuté -> Nginx relancé (19:25:34) -> alerte resolved sur Slack. Délai total : 5 secondes (exigence du sujet : <60s). Sudoers vérifié limité à une seule commande exacte (`systemctl restart nginx.service`), aucune élévation root globale.

## TP COMPLET — Bilan final

Les 4 jalons (A, B, C, D) sont implémentés et **revalidés en VM le 7 septembre 2026**. Compte-rendu : `docs/tests-de-validation.md` (C5.3.3). Dossier de soutenance : `docs/correspondance-grille-bloc5.md`.

- [x] Jalon A — fw-router : DROP par défaut, FORWARD 9100, 10051, 3100, 9095 (timeout SSH 22, routes statiques)
- [x] Jalon A — défense en profondeur nftables web-prod et supervision
- [x] Jalon A — routage statique inter-zones via fw-router (systemd)
- [x] Jalon B — TLS v1.3 + bcrypt Node Exporter (401 sans credentials)
- [x] Jalon B — Prometheus scrape HTTPS + Basic Auth (`health=up`)
- [x] Jalon B — PSK Zabbix (heartbeat working again 20:09 UTC le 7 sept.)
- [x] Jalon C — Promtail → Loki (`nginx_access`, `nginx_error`) + dashboard Grafana M2-Shop
- [x] Jalon D — crash test 21:13:44 UTC : firing → webhook 204 → Nginx relancé < 1 s
