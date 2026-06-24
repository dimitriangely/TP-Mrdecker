# TP 2 SNMP — Mono-machine Linux (Agent & Manager)

## Objectif

Utiliser les outils en ligne de commande `net-snmp` pour interroger un agent SNMP local, explorer la MIB HOST-RESOURCES-MIB et récupérer des métriques système (RAM, charge CPU) via SNMP.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  VM Ubuntu 20.04 (Vagrant + VirtualBox)             │
│  IP : 192.168.56.10                                 │
│                                                     │
│  ┌─────────────┐    UDP:161     ┌─────────────┐     │
│  │  snmpd      │◀──────────────│  snmpget    │     │
│  │  (agent)    │               │  snmpwalk   │     │
│  │  port 161   │               │  (manager)  │     │
│  └─────────────┘               └─────────────┘     │
│         Agent et Manager sur la même machine        │
└─────────────────────────────────────────────────────┘
```

---

## Prérequis

- [VirtualBox 7.x](https://www.virtualbox.org/)
- [Vagrant](https://www.vagrantup.com/)
- VM provisionnée via le `Vagrantfile` et `playbook.yml` du projet

---

## Structure du projet

```
tp2/
├── Vagrantfile
└── playbook.yml
```

---

## Fichiers

### Vagrantfile

```ruby
Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/focal64"
  config.vm.network "private_network", ip: "192.168.56.10"

  config.vm.provision "ansible_local" do |ansible|
    ansible.playbook = "playbook.yml"
  end
end
```

### playbook.yml

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

    - name: Configurer la communauté public
      lineinfile:
        path: /etc/snmp/snmpd.conf
        regexp: '^rocommunity'
        line: 'rocommunity public 192.168.56.0/24'
        backup: yes

    - name: Supprimer toute directive agentAddress existante
      lineinfile:
        path: /etc/snmp/snmpd.conf
        regexp: '^[aA]gent[aA]ddress'
        state: absent

    - name: Ajouter agentAddress correct
      lineinfile:
        path: /etc/snmp/snmpd.conf
        line: 'agentAddress udp:0.0.0.0:161'

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

    - name: Démarrer et activer snmpd
      service:
        name: snmpd
        state: restarted
        enabled: yes

    - name: Ouvrir le port 161 UFW
      ufw:
        rule: allow
        port: '161'
        proto: udp
```

---

## Déploiement

```powershell
# Démarrer et provisionner la VM
vagrant up

# Accéder à la VM
vagrant ssh

# Détruire et recréer (validation reproductibilité)
vagrant destroy -f puis vagrant up
```

---

## Manipulation avec le Manager

### snmpget — Récupérer une valeur précise

```bash
# Nom de la machine
snmpget -v2c -c public localhost .1.3.6.1.2.1.1.5.0

# Uptime
snmpget -v2c -c public localhost .1.3.6.1.2.1.1.3.0
```

### snmpwalk — Parcourir une branche complète

```bash
# Branche system complète
snmpwalk -v2c -c public localhost system

# Branche HOST-RESOURCES-MIB complète
snmpwalk -v2c -c public localhost .1.3.6.1.2.1.25
```

---

## Exercice — Charge CPU et utilisation RAM via HOST-RESOURCES-MIB

### RAM

```bash
# RAM totale
snmpget -v2c -c public localhost 1.3.6.1.2.1.25.2.2.0

# Détail stockage (RAM physique, swap, disques)
snmpwalk -v2c -c public localhost 1.3.6.1.2.1.25.2.3
```

**Calcul du pourcentage RAM utilisée :**

```bash
# hrStorageSize.1 = RAM totale en unités de 1024 octets
# hrStorageUsed.1 = RAM utilisée en unités de 1024 octets
snmpget -v2c -c public localhost 1.3.6.1.2.1.25.2.3.1.5.1  # taille totale
snmpget -v2c -c public localhost 1.3.6.1.2.1.25.2.3.1.6.1  # utilisée

# Calcul pourcentage
echo "scale=2; <hrStorageUsed> * 100 / <hrStorageSize>" | bc
```

### CPU — Load Average (UCD-SNMP-MIB)

> **Note** : `hrProcessorLoad` (HOST-RESOURCES-MIB) n'est pas exposé par défaut sur Ubuntu 20.04. On utilise UCD-SNMP-MIB qui expose le load average Linux natif via `/proc/loadavg`.

```bash
# Load average 1 minute
snmpget -v2c -c public localhost 1.3.6.1.4.1.2021.10.1.3.1

# Load average 5 minutes
snmpget -v2c -c public localhost 1.3.6.1.4.1.2021.10.1.3.2

# Load average 15 minutes
snmpget -v2c -c public localhost 1.3.6.1.4.1.2021.10.1.3.3
```

---

## Résultats obtenus

### RAM

| OID | Nom | Valeur | Interprétation |
|---|---|---|---|
| `1.3.6.1.2.1.25.2.2.0` | hrMemorySize | 987984 KB | ~964 MB RAM totale |
| `1.3.6.1.2.1.25.2.3.1.5.1` | hrStorageSize (Physical memory) | 987984 KB | ~964 MB |
| `1.3.6.1.2.1.25.2.3.1.6.1` | hrStorageUsed (Physical memory) | 685800 KB | ~670 MB utilisés |
| calcul | RAM % utilisée | **69.41%** | Charge normale |

### Stockages détectés

| Index | Nom | Type |
|---|---|---|
| 1 | Physical memory | RAM |
| 3 | Virtual memory | RAM + Swap |
| 6 | Memory buffers | Buffers kernel |
| 7 | Cached memory | Cache kernel |
| 8 | Shared memory | Mémoire partagée |
| 10 | Swap space | Swap |
| 36 | / | Disque racine |

### Load Average CPU

| OID | Période | Valeur | Interprétation |
|---|---|---|---|
| `1.3.6.1.4.1.2021.10.1.3.1` | 1 minute | 0.50 | Post-provisioning |
| `1.3.6.1.4.1.2021.10.1.3.2` | 5 minutes | 0.61 | Post-provisioning |
| `1.3.6.1.4.1.2021.10.1.3.3` | 15 minutes | 0.28 | Post-provisioning |

> Les valeurs post-provisioning sont élevées car Ansible vient de terminer son exécution. En régime stable le load average descend à ~0.01 sur cette VM idle.

> **Lecture du load average** : sur une VM monocore, une valeur < 1.0 signifie qu'aucun processus n'attend le CPU — la machine n'est pas saturée.

---

## OIDs clés utilisés

| Nom | OID | MIB | Description |
|---|---|---|---|
| sysName | `1.3.6.1.2.1.1.5.0` | MIB-2 | Nom de la machine |
| sysUpTime | `1.3.6.1.2.1.1.3.0` | MIB-2 | Uptime |
| hrMemorySize | `1.3.6.1.2.1.25.2.2.0` | HOST-RESOURCES-MIB | RAM totale (KB) |
| hrStorageSize | `1.3.6.1.2.1.25.2.3.1.5.1` | HOST-RESOURCES-MIB | Taille stockage (KB) |
| hrStorageUsed | `1.3.6.1.2.1.25.2.3.1.6.1` | HOST-RESOURCES-MIB | Stockage utilisé (KB) |
| laLoad (1 min) | `1.3.6.1.4.1.2021.10.1.3.1` | UCD-SNMP-MIB | Load average 1 min |
| laLoad (5 min) | `1.3.6.1.4.1.2021.10.1.3.2` | UCD-SNMP-MIB | Load average 5 min |
| laLoad (15 min) | `1.3.6.1.4.1.2021.10.1.3.3` | UCD-SNMP-MIB | Load average 15 min |

---

## Points techniques notables

### Vue systemonly — restriction d'accès par défaut

Ubuntu 22.04 configure snmpd avec une vue restreinte `systemonly` qui n'expose que :
- `.1.3.6.1.2.1.1` — groupe system (MIB-2)
- `.1.3.6.1.2.1.25.1` — hrSystem uniquement

Pour accéder à `hrStorage`, `hrProcessor` et UCD-SNMP-MIB, il faut explicitement étendre la vue dans `/etc/snmp/snmpd.conf` :

```
view systemonly included .1.3.6.1.2.1.25
view systemonly included .1.3.6.1.4.1.2021
```

### hrProcessorLoad non disponible sur Ubuntu 22.04

`hrProcessorLoad` (`1.3.6.1.2.1.25.3.3.1.2`) n'est pas exposé par le paquet `snmpd` d'Ubuntu sans modules additionnels. Le contournement standard est UCD-SNMP-MIB qui lit directement `/proc/loadavg`.

---

## Compétences mobilisées

- SNMP v2c — communauté, OID, MIB, walk vs get
- HOST-RESOURCES-MIB — métriques système (RAM, stockage, CPU)
- UCD-SNMP-MIB — load average Linux via SNMP
- Ansible `lineinfile` — extension de configuration idempotente
- Debug SNMP — identification des restrictions de vue snmpd
- IaC reproductible — `vagrant destroy && vagrant up` sans intervention manuelle