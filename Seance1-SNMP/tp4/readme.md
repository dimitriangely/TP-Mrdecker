# TP 4 SNMP — Sécurisation avec SNMPv3

## Objectif

Configurer SNMPv3 avec authentification SHA et chiffrement AES pour sécuriser les échanges SNMP. Démontrer par capture de trames la différence entre SNMPv2c (données en clair) et SNMPv3 authPriv (données chiffrées).

---

## Concepts clés SNMPv3

SNMPv3 remplace les communautés par des utilisateurs associés à des niveaux de sécurité :

| Niveau | Authentification | Chiffrement | Usage |
|---|---|---|---|
| `noAuthNoPriv` | Non | Non | Peu d'intérêt — équivalent SNMPv2c sans communauté |
| `authNoPriv` | Oui (SHA/MD5) | Non | Authentification mais données lisibles en clair |
| `authPriv` | Oui (SHA/MD5) | Oui (AES/DES) | Standard recommandé en production |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Poste Windows (hôte)                                       │
│                                                             │
│  ┌──────────────────────┐      ┌──────────────────────┐     │
│  │  VM Manager          │      │  VM Agent            │     │
│  │  snmp-manager        │      │  snmp-agent          │     │
│  │  192.168.56.10       │      │  192.168.56.20       │     │
│  │                      │      │                      │     │
│  │  snmp (client v3)    │◀────▶│  snmpd + USM user    │     │
│  │  snmptrapd :162      │◀────▶│  admin_sec (SHA+AES) │     │
│  └──────────────────────┘      └──────────────────────┘     │
│           Réseau host-only : 192.168.56.0/24                │
└─────────────────────────────────────────────────────────────┘
```

---

## Prérequis

- [VirtualBox 7.x](https://www.virtualbox.org/)
- [Vagrant](https://www.vagrantup.com/)

---

## Structure du projet

```
tp4/
├── Vagrantfile
├── playbook_manager.yml
└── playbook_agent.yml
```

---

## Fichiers

### Vagrantfile

```ruby
Vagrant.configure("2") do |config|

  config.vm.define "manager" do |manager|
    manager.vm.box = "ubuntu/focal64"
    manager.vm.hostname = "snmp-manager"
    manager.vm.network "private_network", ip: "192.168.56.10"

    manager.vm.provider "virtualbox" do |vb|
      vb.name = "SNMP-Manager-V3"
      vb.memory = 1024
    end

    manager.vm.provision "ansible_local" do |ansible|
      ansible.playbook = "playbook_manager.yml"
    end
  end

  config.vm.define "agent" do |agent|
    agent.vm.box = "ubuntu/focal64"
    agent.vm.hostname = "snmp-agent"
    agent.vm.network "private_network", ip: "192.168.56.20"

    agent.vm.provider "virtualbox" do |vb|
      vb.name = "SNMP-Agent-V3"
      vb.memory = 1024
    end

    agent.vm.provision "ansible_local" do |ansible|
      ansible.playbook = "playbook_agent.yml"
    end
  end

end
```

### playbook_manager.yml

```yaml
---
- hosts: all
  become: true
  tasks:

    - name: Installer snmp, snmptrapd et snmp-mibs-downloader
      apt:
        name:
          - snmp
          - snmptrapd
          - snmp-mibs-downloader
        state: present
        update_cache: yes

    - name: Télécharger les MIBs standard
      command: download-mibs
      args:
        creates: /usr/share/snmp/mibs/ietf/IF-MIB

    - name: Activer toutes les MIBs
      lineinfile:
        path: /etc/snmp/snmp.conf
        regexp: '^mibs'
        line: 'mibs +ALL'
        create: yes

    - name: Créer le fichier de log pour les traps
      file:
        path: /var/log/snmptrapd.log
        state: touch
        owner: root
        group: root
        mode: '0644'

    - name: Configurer snmptrapd
      copy:
        dest: /etc/snmp/snmptrapd.conf
        content: |
          authCommunity log,execute,net supervision
          createUser admin_sec SHA PassAuth123 AES PassPriv123
          authUser log,execute,net admin_sec authPriv

    - name: Créer le répertoire override systemd
      file:
        path: /etc/systemd/system/snmptrapd.service.d
        state: directory
        mode: '0755'

    - name: Override systemd snmptrapd
      copy:
        dest: /etc/systemd/system/snmptrapd.service.d/override.conf
        content: |
          [Service]
          ExecStart=
          ExecStart=/usr/sbin/snmptrapd -Lf /var/log/snmptrapd.log -f -p /run/snmptrapd.pid

    - name: Recharger systemd
      systemd:
        daemon_reload: yes

    - name: Démarrer et activer snmptrapd
      service:
        name: snmptrapd
        state: restarted
        enabled: yes

    - name: Ouvrir le port 162 UDP
      ufw:
        rule: allow
        port: '162'
        proto: udp
```

### playbook_agent.yml

```yaml
---
- hosts: all
  become: true
  tasks:

    - name: Installer snmpd, client snmp et libsnmp-dev
      apt:
        name:
          - snmpd
          - snmp
          - libsnmp-dev
        state: present
        update_cache: yes

    - name: Arrêter snmpd avant création utilisateur SNMPv3
      service:
        name: snmpd
        state: stopped

    - name: Créer l'utilisateur SNMPv3 admin_sec
      command: >
        net-snmp-config --create-snmpv3-user
        -a SHA -A PassAuth123
        -x AES -X PassPriv123
        admin_sec
      args:
        creates: /var/lib/snmp/.admin_sec_created

    - name: Marquer l'utilisateur admin_sec comme créé
      file:
        path: /var/lib/snmp/.admin_sec_created
        state: touch

    - name: Supprimer toute directive agentAddress existante
      lineinfile:
        path: /etc/snmp/snmpd.conf
        regexp: '^[aA]gent[aA]ddress'
        state: absent

    - name: Ajouter agentAddress sur toutes les interfaces
      lineinfile:
        path: /etc/snmp/snmpd.conf
        line: 'agentAddress udp:0.0.0.0:161'

    - name: Supprimer sysContact statique
      lineinfile:
        path: /etc/snmp/snmpd.conf
        regexp: '^sysContact'
        state: absent

    - name: Supprimer sysLocation statique
      lineinfile:
        path: /etc/snmp/snmpd.conf
        regexp: '^sysLocation'
        state: absent

    - name: Étendre la vue pour IF-MIB
      lineinfile:
        path: /etc/snmp/snmpd.conf
        line: 'view systemonly included .1.3.6.1.2.1.2'
        insertafter: EOF

    - name: Étendre la vue pour HOST-RESOURCES-MIB
      lineinfile:
        path: /etc/snmp/snmpd.conf
        line: 'view systemonly included .1.3.6.1.2.1.25'
        insertafter: EOF

    - name: Étendre la vue pour UCD-SNMP-MIB
      lineinfile:
        path: /etc/snmp/snmpd.conf
        line: 'view systemonly included .1.3.6.1.4.1.2021'
        insertafter: EOF

    - name: Configurer accès SNMPv3 pour admin_sec
      blockinfile:
        path: /etc/snmp/snmpd.conf
        block: |
          rouser admin_sec authPriv
          trap2sink 192.168.56.10 supervision
          trapsess -v3 -u admin_sec -l authPriv -a SHA -A PassAuth123 -x AES -X PassPriv123 192.168.56.10

    - name: Ouvrir le port 161 UDP
      ufw:
        rule: allow
        port: '161'
        proto: udp

    - name: Démarrer et activer snmpd
      service:
        name: snmpd
        state: started
        enabled: yes
```

---

## Déploiement

```powershell
# Démarrer les deux VMs
vagrant up

# SSH sur une VM spécifique
vagrant ssh manager
vagrant ssh agent

# Détruire et recréer
vagrant destroy -f puis vagrant up
```

---

## Utilisation de SNMPv3

### Syntaxe générale

```bash
snmpget -v3 -u <user> -l <niveau> -a <auth_algo> -A <auth_pass> -x <priv_algo> -X <priv_pass> <cible> <OID>
```

| Paramètre | Description | Valeur |
|---|---|---|
| `-v3` | Version SNMP | 3 |
| `-u` | Nom d'utilisateur | `admin_sec` |
| `-l` | Niveau de sécurité | `noAuthNoPriv`, `authNoPriv`, `authPriv` |
| `-a` | Algorithme d'authentification | `SHA`, `MD5` |
| `-A` | Mot de passe d'authentification | `PassAuth123` |
| `-x` | Algorithme de chiffrement | `AES`, `DES` |
| `-X` | Mot de passe de chiffrement | `PassPriv123` |

### Exemples

```bash
# Lire le nom de la machine
snmpget -v3 -u admin_sec -l authPriv \
  -a SHA -A PassAuth123 \
  -x AES -X PassPriv123 \
  192.168.56.20 SNMPv2-MIB::sysName.0

# Walk complet du groupe system
snmpwalk -v3 -u admin_sec -l authPriv \
  -a SHA -A PassAuth123 \
  -x AES -X PassPriv123 \
  192.168.56.20 system

# Interfaces réseau
snmpwalk -v3 -u admin_sec -l authPriv \
  -a SHA -A PassAuth123 \
  -x AES -X PassPriv123 \
  192.168.56.20 IF-MIB::ifDescr
```

---

## Comparaison des niveaux de sécurité

```bash
# noAuthNoPriv — refusé car rouser exige authPriv minimum
snmpget -v3 -u admin_sec -l noAuthNoPriv 192.168.56.20 SNMPv2-MIB::sysName.0
# → authorizationError (access denied)

# authNoPriv — accepté, données en clair
snmpget -v3 -u admin_sec -l authNoPriv -a SHA -A PassAuth123 192.168.56.20 SNMPv2-MIB::sysName.0
# → SNMPv2-MIB::sysName.0 = STRING: snmp-agent

# authPriv — accepté, données chiffrées
snmpget -v3 -u admin_sec -l authPriv -a SHA -A PassAuth123 -x AES -X PassPriv123 192.168.56.20 SNMPv2-MIB::sysName.0
# → SNMPv2-MIB::sysName.0 = STRING: snmp-agent
```

> `noAuthNoPriv` est refusé car la directive `rouser admin_sec authPriv` dans `snmpd.conf` définit `authPriv` comme niveau minimum requis. Pour accepter tous les niveaux, utiliser `rouser admin_sec` sans niveau.

---

## Analyse de trames — Démonstration du chiffrement

### Capture avec tcpdump

```bash
# Lancer la capture sur l'interface host-only
sudo tcpdump -i enp0s8 -w /tmp/snmp_capture.pcap port 161 &

# Envoyer une requête SNMPv2c (en clair)
snmpget -v2c -c supervision 192.168.56.20 SNMPv2-MIB::sysName.0

# Envoyer une requête SNMPv3 (chiffrée)
snmpget -v3 -u admin_sec -l authPriv \
  -a SHA -A PassAuth123 -x AES -X PassPriv123 \
  192.168.56.20 SNMPv2-MIB::sysName.0

# Arrêter la capture
sudo pkill tcpdump
```

### Analyse avec tshark

```bash
sudo apt install tshark -y
tshark -r /tmp/snmp_capture.pcap -Y snmp
```

### Résultats obtenus

**SNMPv2c — données en clair :**
```
version: v2c (1)
community: supervision        ← communauté visible en clair
data: get-request
    Object Name: 1.3.6.1.2.1.1.5.0   ← OID visible en clair
```

**SNMPv3 authPriv — données chiffrées :**
```
msgVersion: snmpv3 (3)
msgFlags: 07
    Encrypted: Set            ← chiffrement AES actif
    Authenticated: Set        ← authentification SHA active
msgUserName: admin_sec
msgAuthenticationParameters: 817dfe31a85e40bc5b9a7bda  ← HMAC-SHA
msgPrivacyParameters: 1042536f58b2cd1a                  ← IV AES
encryptedPDU: privKey Unknown ← contenu illisible sans la clé
```

### Tableau comparatif

| | SNMPv2c | SNMPv3 authPriv |
|---|---|---|
| Identification | Communauté `supervision` visible | Utilisateur `admin_sec` visible |
| Contenu (PDU) | OID + valeur en clair | `encryptedPDU` illisible |
| Authentification | Aucune | HMAC-SHA |
| Chiffrement | Aucun | AES-128 |
| Replay possible | Oui | Non (engineBoots + engineTime) |

---

## Points techniques notables

### createUser — directive one-shot

La commande `net-snmp-config --create-snmpv3-user` écrit une ligne `createUser` dans `/var/lib/snmp/snmpd.conf`. Au démarrage de snmpd, cette ligne est consommée et remplacée par une entrée `usmUser` avec les clés dérivées chiffrées :

```
usmUser 1 3 0x80001f88...  ← engineID
0x61646d696e5f736563        ← "admin_sec" en hex
NULL .1.3.6.1.6.3.10.1.1.3  ← SHA
0x63bad214...               ← clé d'auth dérivée (jamais le mot de passe)
.1.3.6.1.6.3.10.1.2.4       ← AES
0x19c58deb...               ← clé de chiffrement dérivée
```

Les mots de passe ne sont jamais stockés en clair.

### snmpd doit être arrêté pendant createUser

Si snmpd tourne pendant l'exécution de `net-snmp-config`, il écrase `/var/lib/snmp/snmpd.conf` au prochain redémarrage et efface la ligne `createUser` avant qu'elle soit traitée. L'ordre strict est : stop → createUser → start.

### Idempotence avec fichier marqueur

`net-snmp-config --create-snmpv3-user` n'est pas idempotent nativement — relancé deux fois, il crée l'utilisateur en double. La solution est un fichier marqueur :

```yaml
args:
  creates: /var/lib/snmp/.admin_sec_created
```

Le fichier `.admin_sec_created` est créé par la task suivante et sert de sentinelle pour les exécutions ultérieures.

### libsnmp-dev requis pour net-snmp-config

`net-snmp-config` n'est pas inclus dans le paquet `snmpd` — il fait partie de `libsnmp-dev`. Sans ce paquet, la commande retourne `command not found`.

### Discovery SNMPv3

Avant d'envoyer une requête chiffrée, le manager effectue un échange de découverte pour obtenir l'`engineID` de l'agent. C'est visible dans la capture :
- Paquet discovery : `Encrypted: Not set`, `msgUserName: (vide)`
- Paquet requête : `Encrypted: Set`, `msgUserName: admin_sec`

---

## Compétences mobilisées

- SNMPv3 USM (User-based Security Model) — utilisateurs, niveaux de sécurité
- Algorithmes cryptographiques SNMP — SHA pour l'authentification, AES pour le chiffrement
- `net-snmp-config` — création d'utilisateurs SNMPv3 en ligne de commande
- Analyse de trames — tcpdump + tshark pour comparer SNMPv2c et SNMPv3
- Idempotence Ansible — fichier marqueur pour les commandes non idempotentes nativement
- Dérivation de clés SNMP — les mots de passe ne sont jamais stockés en clair