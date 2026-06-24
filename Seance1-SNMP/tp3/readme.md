# TP 3 SNMP — Architecture Distante (Manager + Agent)

## Objectif

Simuler un monitoring réseau réel entre un Manager et un Agent distant via SNMP. Configurer l'envoi automatique de traps (alertes) de l'agent vers le manager sur deux scénarios : redémarrage et coupure d'interface réseau.

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
│  │  snmp (client)       │◀────▶│  snmpd (agent)       │     │
│  │  snmptrapd :162      │◀────▶│  trap → .10:162      │     │
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
tp3/
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
      vb.name = "SNMP-Manager"
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
      vb.name = "SNMP-Agent"
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

    - name: Créer le répertoire override systemd
      file:
        path: /etc/systemd/system/snmptrapd.service.d
        state: directory
        mode: '0755'

    - name: Override systemd snmptrapd pour logger dans un fichier
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

    - name: Installer snmpd et client snmp
      apt:
        name:
          - snmpd
          - snmp
        state: present
        update_cache: yes

    - name: Supprimer toute directive agentAddress existante
      lineinfile:
        path: /etc/snmp/snmpd.conf
        regexp: '^[aA]gent[aA]ddress'
        state: absent

    - name: Ajouter agentAddress sur toutes les interfaces
      lineinfile:
        path: /etc/snmp/snmpd.conf
        line: 'agentAddress udp:0.0.0.0:161'

    - name: Configurer la communauté supervision (read-only)
      lineinfile:
        path: /etc/snmp/snmpd.conf
        regexp: '^rocommunity'
        line: 'rocommunity supervision 192.168.56.10'

    - name: Ajouter la communauté admin (read-write)
      lineinfile:
        path: /etc/snmp/snmpd.conf
        line: 'rwcommunity admin 192.168.56.10'
        insertafter: EOF

    - name: Supprimer sysContact statique pour autoriser snmpset
      lineinfile:
        path: /etc/snmp/snmpd.conf
        regexp: '^sysContact'
        state: absent

    - name: Supprimer sysLocation statique pour autoriser snmpset
      lineinfile:
        path: /etc/snmp/snmpd.conf
        regexp: '^sysLocation'
        state: absent

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

    - name: Étendre la vue pour IF-MIB
      lineinfile:
        path: /etc/snmp/snmpd.conf
        line: 'view systemonly included .1.3.6.1.2.1.2'
        insertafter: EOF

    - name: Configurer les traps vers le Manager
      blockinfile:
        path: /etc/snmp/snmpd.conf
        block: |
          trap2sink 192.168.56.10 supervision
          informsink 192.168.56.10 supervision
          monitor -r 60 -e linkDown "Interface down" ifOperStatus.2 != 1

    - name: Ouvrir le port 161 UDP
      ufw:
        rule: allow
        port: '161'
        proto: udp

    - name: Démarrer et activer snmpd
      service:
        name: snmpd
        state: restarted
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

# Redémarrer une VM spécifique
vagrant reload agent

# Détruire et recréer (validation reproductibilité)
vagrant destroy -f && vagrant up
```

---

## Scénario 1 — Supervision distante des interfaces réseau

Depuis le manager, interroge les interfaces de l'agent :

```bash
# Noms des interfaces
snmpwalk -v2c -c supervision 192.168.56.20 IF-MIB::ifDescr

# État des interfaces
snmpwalk -v2c -c supervision 192.168.56.20 IF-MIB::ifOperStatus
```

Résultats obtenus :

| Index | Interface | État |
|---|---|---|
| 1 | lo (loopback) | up(1) |
| 2 | enp0s3 (NAT) | up(1) |
| 3 | enp0s8 (host-only) | up(1) |

---

## Scénario 2 — Trap coldStart (redémarrage)

Sur le manager, surveille les traps en temps réel :

```bash
sudo tail -f /var/log/snmptrapd.log
```

Depuis Windows, redémarre l'agent :

```powershell
vagrant reload agent
```

Au démarrage de snmpd, une trap `coldStart` est envoyée automatiquement au manager :

```
2026-06-24 11:02:43 [UDP: [192.168.56.20]:48392->[192.168.56.10]:162]:
iso.3.6.1.2.1.1.3.0 = Timeticks: (5) 0:00:00.05
iso.3.6.1.6.3.1.1.4.1.0 = OID: iso.3.6.1.6.3.1.1.5.1
```

`iso.3.6.1.6.3.1.1.5.1` = OID de la trap **coldStart**.

---

## Scénario 3 — Trap linkDown (coupure d'interface)

Le monitor snmpd vérifie toutes les 60 secondes l'état de `ifOperStatus.2` (enp0s3). Si l'interface tombe, une trap `linkDown` est envoyée au manager.

Depuis l'agent, coupe l'interface et la remet up automatiquement après 10 secondes :

```bash
sudo bash -c 'ip link set enp0s3 down; sleep 10; ip link set enp0s3 up' &
```

La trap est reçue sur le manager dans les 60 secondes :

```
2026-06-24 11:02:43 [UDP: [192.168.56.20]:34376->[192.168.56.10]:162]:
iso.3.6.1.2.1.1.3.0 = Timeticks: (5) 0:00:00.05
iso.3.6.1.6.3.1.1.4.1.0 = OID: iso.3.6.1.6.3.1.1.5.1
iso.3.6.1.4.1.8072.3.2.10
```

---

## OIDs des traps standard

| OID | Nom | Déclencheur |
|---|---|---|
| `1.3.6.1.6.3.1.1.5.1` | coldStart | Démarrage de l'agent |
| `1.3.6.1.6.3.1.1.5.2` | warmStart | Redémarrage sans réinitialisation |
| `1.3.6.1.6.3.1.1.5.3` | linkDown | Interface réseau qui tombe |
| `1.3.6.1.6.3.1.1.5.4` | linkUp | Interface réseau qui remonte |
| `1.3.6.1.4.1.8072.4.0.2` | nsNotifyShutdown | Arrêt de snmpd |

---

## Commandes avancées

### snmptranslate — Convertir noms et OIDs

`snmptranslate` permet de naviguer dans la MIB sans interroger un agent — utile pour trouver un OID ou comprendre ce qu'il représente.

```bash
# Nom symbolique → OID numérique
snmptranslate -On IF-MIB::ifDescr
snmptranslate -On SNMPv2-MIB::sysName.0

# OID numérique → description complète
snmptranslate -Td 1.3.6.1.2.1.2.2.1.2
snmptranslate -Td 1.3.6.1.2.1.1.5.0

# Description complète par nom symbolique
snmptranslate -Td IF-MIB::ifOperStatus
snmptranslate -Td HOST-RESOURCES-MIB::hrMemorySize
```

La description `-Td` révèle le type (`SYNTAX`), l'accès (`MAX-ACCESS`), le statut et la documentation RFC de l'OID. C'est ce qui permet de savoir si un OID est modifiable avec `snmpset` avant de tenter l'opération.

---

### snmpset — Modifier une valeur sur l'agent

`snmpset` nécessite une communauté `rwcommunity` sur l'agent et un OID avec `MAX-ACCESS read-write`.

```bash
# Syntaxe : snmpset -v2c -c <communauté_rw> <cible> <OID> <type> <valeur>

# Modifier le contact administrateur
snmpset -v2c -c admin 192.168.56.20 SNMPv2-MIB::sysContact.0 s "admin@supervision.lab"

# Modifier la localisation
snmpset -v2c -c admin 192.168.56.20 SNMPv2-MIB::sysLocation.0 s "Datacenter-Lab-Paris"

# Vérifier les modifications
snmpget -v2c -c supervision 192.168.56.20 SNMPv2-MIB::sysContact.0
snmpget -v2c -c supervision 192.168.56.20 SNMPv2-MIB::sysLocation.0
```

Types de valeurs pour `snmpset` :

| Lettre | Type | Exemple |
|---|---|---|
| `s` | String | `s "valeur"` |
| `i` | Integer | `i 42` |
| `t` | TimeTicks | `t 0` |
| `a` | IP Address | `a 192.168.1.1` |

> **Attention** : si `sysContact` ou `sysLocation` sont définis statiquement dans `/etc/snmp/snmpd.conf`, snmpd les protège en écriture même avec une communauté `rwcommunity`. Il faut supprimer ces lignes statiques pour autoriser la modification via SNMP — c'est ce que fait le playbook_agent.yml avec les tasks `state: absent`.

---

## Points techniques notables

### Override systemd snmptrapd

Ubuntu 22.04 lance snmptrapd avec `-LOw` (log syslog) dans le service systemd, ignorant `/etc/default/snmptrapd`. Pour logger dans un fichier, un override est nécessaire :

```
/etc/systemd/system/snmptrapd.service.d/override.conf
[Service]
ExecStart=
ExecStart=/usr/sbin/snmptrapd -Lf /var/log/snmptrapd.log -f -p /run/snmptrapd.pid
```

La première ligne `ExecStart=` vide est obligatoire — sans elle systemd cumule les deux directives.

### MIBs standard non installées par défaut

Ubuntu 22.04 n'inclut pas les MIBs IETF standard (IF-MIB, SNMPv2-MIB...) pour des raisons de licence. Le paquet `snmp-mibs-downloader` les télécharge depuis les RFCs. Sans elles, `IF-MIB::ifDescr` retourne `Unknown Object Identifier`.

### Contrainte de la trap linkDown

La trap linkDown ne peut pas être envoyée sur l'interface qui tombe si c'est la seule interface vers le manager. Dans ce lab, `enp0s8` (host-only) sert à la supervision et `enp0s3` (NAT) peut être coupée sans perdre la connectivité avec le manager.

### Warning SNMPv2-PDU

Le warning `Bad operator (INTEGER): At line 73 in /usr/share/snmp/mibs/ietf/SNMPv2-PDU` est un bug connu du paquet Ubuntu 20.04. Il n'affecte pas le fonctionnement et peut être ignoré.

### snmpset — Erreur notWritable sur sysContact/sysLocation

Quand `sysContact` et `sysLocation` sont définis statiquement dans `/etc/snmp/snmpd.conf`, snmpd les considère comme des valeurs gérées localement et refuse toute modification via SNMP, même avec une communauté `rwcommunity`. L'erreur retournée est `notWritable (That object does not support modification)`. La solution est de supprimer ces lignes statiques du fichier de config — snmpd accepte alors les modifications via `snmpset`.

---

## Compétences mobilisées

- Vagrant multi-machines — provisioning de plusieurs VMs depuis un seul Vagrantfile
- Ansible multi-playbooks — séparation des rôles manager/agent
- SNMP Traps — coldStart, linkDown, configuration de `trap2sink` et `monitor`
- snmptrapd — réception et logging des traps, override systemd
- IF-MIB — supervision des interfaces réseau distantes
- MIBs IETF — installation et activation sur Ubuntu 22.04
- Debug systemd — override de service pour modifier les options de démarrage
- snmptranslate — exploration de la MIB, conversion noms/OIDs, lecture des descriptions RFC
- snmpset — modification à distance de valeurs SNMP avec communauté read-write