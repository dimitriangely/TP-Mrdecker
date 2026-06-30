# Matrice de Flux Réglementaire — TP Observabilité Sécurisée

Document destiné à la Section 1 (DAT) du Dossier d'Architecture et d'Exploitation.

| Zone Source  | IP Source    | Zone Dest.    | IP Dest.     | Protocole | Port  | Sens d'initiation     | Justification                          |
|---------------|--------------|----------------|--------------|-----------|-------|------------------------|------------------------------------------|
| DMZ Admin     | 10.0.10.5    | DMZ Prod       | 10.0.20.20   | TCP       | 9100  | Admin -> Prod          | Scraping Prometheus, TLS v1.3 + Basic Auth |
| DMZ Prod      | 10.0.20.20   | DMZ Admin      | 10.0.10.5    | TCP       | 10051 | Prod -> Admin          | Zabbix Agent mode Actif (Push), PSK chiffré |
| DMZ Prod      | 10.0.20.20   | DMZ Admin      | 10.0.10.5    | TCP       | 3100  | Prod -> Admin          | Promtail -> Loki, envoi des logs Nginx     |
| DMZ Admin     | 10.0.10.5    | DMZ Prod       | 10.0.20.20   | TCP       | 9095  | Admin -> Prod          | Alertmanager -> webhook receiver, déclenchement auto-healing |
| DMZ Prod      | 10.0.20.20   | Internet       | -            | TCP       | 443/80| Prod (entrant public)  | Flux web public légitime (Nginx fil rouge) |
| DMZ Admin     | 10.0.10.5    | Internet       | -            | TCP       | 443   | Admin -> Internet      | Webhook sortant unique vers Slack/Discord  |
| Hôte (SRE)    | -            | DMZ Admin      | 10.0.10.5    | TCP       | 3000  | SRE -> Admin           | Accès Grafana en HTTPS uniquement          |

## Règles explicitement interdites (et vérifiées au protocole de recette)

- Aucun flux entrant initié depuis DMZ Admin vers DMZ Prod en dehors du port 9100/TCP.
- Aucun flux initié par le serveur Zabbix (Admin) vers l'agent (Prod) : le mode Push est strict, l'agent initie toujours.
- Toute tentative de connexion directe web-prod <-> supervision en dehors de fw-router est physiquement impossible (pas de réseau privé commun, cf. Vagrantfile).
- Toute tentative depuis web-prod vers supervision sur un port autre que 10051 doit expirer (timeout).

## Statut d'implémentation (mis à jour au fil des sessions)

- [x] Nginx (fil rouge) déployé sur web-prod : HTTPS public (TLS auto-signé), redirection HTTP->HTTPS, logs standards access/error.log prêts pour Promtail (validé en VM : 200 en HTTPS, logs présents)
- [x] Promtail (web-prod) -> Loki (supervision) : validé en VM (targets ready, labels nginx_access/nginx_error confirmés côté Loki)
- [x] Grafana (supervision) avec datasources Prometheus + Loki provisionnées automatiquement : validé en VM (service actif, /api/health = 200)
- [x] Grafana en HTTPS only (certificat auto-signé dédié) — validé en VM : service stable, /api/health = 200 en HTTPS
- [x] Dashboard unifié M2-Shop (req/s, taux erreurs 4xx/5xx, CPU, mémoire, logs bruts) provisionné automatiquement — validé en VM
- [x] Jalon D — Alerte NginxDown (Prometheus + Alertmanager + Slack) — validée en VM : déclenchement quasi instantané (<1s entre l'arrêt du service et le déclenchement de l'alerte), message Slack reçu avec heure/hôte/impact conformes au sujet
- [x] Jalon D — Script d'auto-healing + sudoers chirurgical non-root — validé en VM, protocole de recette complet : coupure Nginx -> alerte firing (19:25:29) -> webhook -> script exécuté -> Nginx relancé (19:25:34) -> alerte resolved sur Slack. Délai total : 5 secondes (exigence du sujet : <60s). Sudoers vérifié limité à une seule commande exacte (`systemctl restart nginx.service`), aucune élévation root globale.

## TP COMPLET — Bilan final

Les 4 jalons du sujet (A, B, C, D) sont implémentés et validés en conditions
réelles sur les 3 VMs Vagrant. Reste à finaliser pour la remise : le Dossier
d'Architecture et d'Exploitation (DAE) complet en PDF (Sections 1, 2, 3), en
s'appuyant sur cette matrice de flux, les captures de validation déjà
réalisées, et les incidents documentés dans le README.

- [x] Jalon A — fw-router : politique DROP par défaut, FORWARD limité à 9100 et 10051 (validé en VM : timeout sur port 22 non autorisé, refus de connexion explicite sur 10051 autorisé)
- [x] Jalon A — défense en profondeur nftables sur web-prod et supervision (validé en VM)
- [x] Jalon A — routage statique inter-zones via fw-router (validé en VM, persistant via systemd)
- [x] Jalon B — TLS v1.3 + bcrypt sur Node Exporter (validé en VM : TLSv1.3 négocié, 401 sans credentials)
- [x] Jalon B — Prometheus scrape HTTPS + Basic Auth + insecure_skip_verify (validé en VM : target health=up, lastError vide)
- [x] Jalon B — PSK Zabbix 64 hex (validé en VM via capture tcpdump : handshakes TLS-PSK répétés réussis, identité PSK visible en clair comme attendu, payload chiffré)
- [ ] Jalon C — Promtail -> Loki, Grafana dashboard unifié (à faire)
- [ ] Jalon D — Alerting webhook + script auto-healing + sudoers chirurgical (à faire)
