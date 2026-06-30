# TP Observabilité Sécurisée — M2-Shop / Workshop ANSSI

## Méthode de travail

Comprendre avant d'exécuter, construire couche par couche, valider à chaque étape
via `ansible_local` (jamais depuis l'hôte Windows). Chaque rôle Ansible correspond
à une VM et à un jalon du sujet ; on ne passe à la couche suivante qu'une fois la
précédente validée par un test concret.

## Topologie

```
web-prod (10.0.20.20)  <--->  fw-router (.20.1 / .10.1)  <--->  supervision (10.0.10.5)
   DMZ Production              cloisonnement Zero-Trust          DMZ Admin
```

3 VMs Debian, aucun réseau privé commun entre web-prod et supervision : tout flux
inter-zone transite obligatoirement par fw-router.

## État d'avancement

**Jalon A (validé en VM)** : socle réseau Zero-Trust complet — cloisonnement nftables,
routage statique inter-zones, timeout sur ports non autorisés, refus de connexion
explicite sur les ports autorisés sans service en écoute.

**Jalon B (validé en VM)** :
- Node Exporter sur `web-prod` : TLS v1.3 forcé (`web-config.yml`), Basic Auth
  avec hash bcrypt généré dynamiquement par Ansible depuis le vault — TLSv1.3
  confirmé, 401 sans credentials confirmé
- Prometheus sur `supervision` : scrape HTTPS du Node Exporter, `insecure_skip_verify`
  (certificat auto-signé), Basic Auth — target `health: up` confirmé
- Zabbix Agent2 (`web-prod`) en mode Actif strict + Zabbix Server/MariaDB
  (`supervision`), chiffrement PSK 64 hex. L'hôte est enregistré côté serveur
  via un script SQL idempotent (contournement documenté en l'absence de
  frontend Zabbix, qui arrivera au Jalon C) — **validé en VM** par capture
  tcpdump : handshakes TLS-PSK répétés réussis sur le port 10051, identité
  PSK visible en clair (normal, ce n'est pas un secret), payload applicatif
  intégralement chiffré.

#### Incidents rencontrés et résolus (Jalon B Zabbix)

1. **`hostid = 0` en base** : le schéma Zabbix n'utilise PAS l'auto-increment
   MySQL pour ses clés primaires ; il gère ses propres compteurs via une table
   interne `ids`. Une `INSERT` sans `hostid` explicite produisait donc une
   ligne invalide (`hostid=0`) que le serveur ignorait silencieusement.
   Corrigé en calculant `MAX(hostid)+1` et en tenant à jour la table `ids`
   (voir `register_host.sql.j2`).
2. **`no suitable signature algorithm` / handshake TLS intermittent** : bug
   d'interopérabilité connu d'OpenSSL 3.0.x (version par défaut sur Debian 12)
   dans la négociation TLS 1.3 pour les cipher suites PSK pures. Résolu par
   mise à jour du paquet `openssl`/`libssl3` suivie d'un redémarrage des
   services `zabbix-agent2` et `zabbix-server`.
3. **`Datasource provisioning error: data source not found` (Grafana 13)** :
   réutiliser le nom du `type` comme `uid` (`uid: Loki`, `uid: Prometheus`)
   entre en conflit avec la résolution interne du nouveau système de
   provisioning de Grafana 13, ce qui fait planter le service entièrement au
   démarrage (boucle de redémarrage infinie, aucun port HTTP/HTTPS ouvert).
   Résolu en utilisant des UID explicitement distincts du nom du type
   (`prometheus_ds`, `loki_ds`).

### Secrets et Ansible Vault

Le mot de passe Basic Auth du Node Exporter est stocké chiffré dans
`ansible/group_vars/all/vault.yml` (Ansible Vault).

Le mot de passe du vault lui-même (`ChangeMe-VaultPass-TP2026` par défaut, à
changer avant tout usage réel) est déposé directement sur chaque VM dans
`/etc/ansible-vault-pass.txt` via un provisioner `shell` dans le `Vagrantfile`,
**avant** le provisioner `ansible_local`. Deux raisons à ce choix de chemin :

1. Ce fichier n'est PAS dans le dossier synchronisé `/vagrant` : un partage
   VirtualBox monté depuis un hôte Windows (`vboxsf`) expose tous les fichiers
   comme exécutables côté invité quels que soient leurs droits réels sous
   Windows, ce qui faisait qu'Ansible tentait d'exécuter `.vault_pass.txt`
   (versions précédentes) comme un script vault au lieu de le lire en texte
   brut.
2. `/etc` est traversable par tous (`755`), contrairement à `/root` (`700`).
   Le plugin `vagrant-ansible_local` vérifie l'existence du fichier via SSH en
   tant qu'utilisateur `vagrant` (non-root) ; un dépôt dans `/root` échoue donc
   silencieusement avec un message trompeur ("does not exist on the guest")
   alors qu'il s'agit en réalité d'un refus de traversée de répertoire.

Le fichier est en `chmod 644` : le processus `ansible-playbook` lui-même
s'exécute en tant qu'utilisateur `vagrant` (l'élévation `become: true` ne
s'applique qu'aux tâches du playbook, pas à la lecture initiale du vault
password file), il doit donc pouvoir le lire. C'est une simplification
acceptée pour ce TP — le mot de passe protège un vault de laboratoire, pas un
secret de production ; dans un contexte réel, on isolerait ce fichier via un
gestionnaire de secrets externe (Vault HashiCorp, Ansible Vault avec un script
de récupération dynamique, etc.) plutôt qu'un fichier en clair sur disque.

Pour changer le mot de passe vault et son contenu :

```bash
# Sur la VM concernée (le mot de passe vault y est maintenant local) :
vagrant ssh web-prod -c "sudo ansible-vault rekey /vagrant/ansible/group_vars/all/vault.yml --vault-password-file /etc/ansible-vault-pass.txt"
```

Pense à mettre à jour la chaîne dans le `Vagrantfile` (les 3 blocs `shell`
inline) si tu changes ce mot de passe, pour que le provisioning reste
automatique sur les 3 VMs.

## Démarrage

```bash
vagrant up
```

Vagrant provisionne chaque VM via `ansible_local` avec `--limit` sur son propre
groupe d'inventaire — pas d'exécution croisée depuis l'hôte.

## Validation Jalon A (à exécuter une fois les VMs up)

Depuis `web-prod`, tenter de joindre `supervision` sur un port NON autorisé doit timeout :

```bash
vagrant ssh web-prod -c "timeout 5 nc -zv 10.0.10.5 22 || echo 'TIMEOUT OK - Zero-Trust validé'"
```

Le flux Zabbix push (10051) initié depuis web-prod doit, lui, passer le routeur
(le service Zabbix Server n'étant pas encore déployé à ce stade, on attend un
refus de connexion TCP — PAS un timeout — preuve que le port traverse bien fw-router) :

```bash
vagrant ssh web-prod -c "timeout 5 nc -zv 10.0.10.5 10051"
```

## Validation Jalon B

Sur `web-prod`, vérifier que Node Exporter écoute en TLS et que l'accès sans
authentification échoue :

```bash
vagrant ssh web-prod -c "sudo ss -tpln | grep 9100"
vagrant ssh web-prod -c "curl -k -s -o /dev/null -w '%{http_code}\n' https://localhost:9100/metrics"
# Attendu : 401 (preuve exigée par le protocole de recette du sujet)
```

Sur `supervision`, vérifier que Prometheus scrape correctement le target (statut UP) :

```bash
vagrant ssh supervision -c "curl -s http://localhost:9090/api/v1/targets | grep -o '\"health\":\"[a-z]*\"'"
```

### Validation Zabbix PSK

Vérifier que l'agent envoie correctement ses données chiffrées (les logs ne
doivent montrer aucune erreur de type "connection refused" ou "wrong PSK") :

```bash
vagrant ssh web-prod -c "sudo tail -30 /var/log/zabbix/zabbix_agent2.log"
vagrant ssh supervision -c "sudo tail -30 /var/log/zabbix/zabbix_server.log"
```

Capture du handshake chiffré pour preuve dans le DAE (Section 2, preuves de
chiffrement), à exécuter sur `fw-router` pendant qu'une donnée est envoyée :

```bash
vagrant ssh fw-router -c "sudo timeout 20 tcpdump -i eth2 port 10051 -nn -X" 
```
Le contenu capturé doit apparaître chiffré (pas de texte en clair lisible),
contrairement à une capture sur un flux non chiffré.

## Structure du repo

```
.
├── Vagrantfile
├── ansible/
│   ├── site.yml
│   ├── inventory/hosts.ini
│   └── roles/
│       ├── common/
│       ├── fw-router/
│       ├── web-prod/
│       └── supervision/
└── docs/
    └── matrice-de-flux.md   (alimente la Section 1 du DAE)
```

## Notes

- `BOX_IMAGE` dans le `Vagrantfile` est positionnée sur `debian/bookworm64` par
  défaut (compatibilité Vagrant Cloud) ; à remplacer par une box Debian 13 si
  disponible localement.
- Les noms d'interfaces réseau (`enp0s8`, `enp0s9`) dans les templates nftables
  sont des valeurs usuelles pour Debian/VirtualBox mais DOIVENT être vérifiées
  via `ip a` après le premier `vagrant up` et corrigées si besoin avant le
  premier `vagrant provision`.
