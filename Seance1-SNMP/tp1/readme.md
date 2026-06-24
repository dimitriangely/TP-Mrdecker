# TP SNMP — Supervision avec agent snmpd et iReasoning MIB Browser

## Objectif

Déployer un agent SNMP sur une VM Linux via Infrastructure as Code (Vagrant + Ansible) et l'interroger depuis un manager Windows (iReasoning MIB Browser) pour récupérer des informations système via la MIB.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Poste Windows (hôte)                               │
│                                                     │
│  iReasoning MIB Browser ──────────────────────────┐ │
│                            UDP:161                 │ │
│  ┌─────────────────────────────────────────────┐  │ │
│  │  VM Ubuntu 20.04 (Vagrant + VirtualBox)     │  │ │
│  │  IP : 192.168.56.10 (host-only)             │◀─┘ │
│  │  snmpd — communauté public — port 161       │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

---

## Prérequis

- [VirtualBox 7.x](https://www.virtualbox.org/)
- [Vagrant](https://www.vagrantup.com/)
- [iReasoning MIB Browser](https://www.ireasoning.com/mibbrowser.shtml) (Personal Edition)

---

## Structure du projet

```
Seance1-SNMP/
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
vagrant destroy -f && vagrant up
```

---

## Validation CLI

Depuis la VM (`vagrant ssh`) :

```bash
# Vérifier que snmpd tourne
sudo systemctl status snmpd

# Vérifier que le port 161 est ouvert
sudo ss -ulnp | grep 161

# Walk complet du groupe system
snmpwalk -v2c -c public 127.0.0.1 1.3.6.1.2.1.1

# Récupérer le nom de la machine (sysName)
snmpget -v2c -c public 127.0.0.1 1.3.6.1.2.1.1.5.0

# Récupérer le temps depuis le dernier démarrage (sysUpTime)
snmpget -v2c -c public 127.0.0.1 1.3.6.1.2.1.1.3.0
```

Résultats attendus :

| OID | Valeur | Signification |
|---|---|---|
| `1.3.6.1.2.1.1.5.0` | `ubuntu-focal` | Nom de la machine (sysName) |
| `1.3.6.1.2.1.1.3.0` | `0:01:09.47` | Uptime depuis démarrage (sysUpTime) |

---

## Validation via iReasoning MIB Browser

1. Ouvrir iReasoning MIB Browser
2. Cliquer sur **Advanced...**
3. Configurer :

| Champ | Valeur |
|---|---|
| Address | `192.168.56.10` |
| Port | `161` |
| Read Community | `public` |
| SNMP Version | `2` (= v2c dans iReasoning) |

4. Cliquer **Ok** puis **Go**
5. Dans la barre OID, taper `.1.3.6.1.2.1.1.5.0` → **Get** → retourne `ubuntu-focal`
6. Taper `.1.3.6.1.2.1.1.3.0` → **Get** → retourne le sysUpTime

Pour explorer l'arborescence complète :
- Déplie dans le panneau gauche : `iso.org.dod.internet.mgmt.mib-2`
- Clic droit sur `system` → **Walk**

---

## OIDs clés du groupe system (MIB-2)

| Nom | OID | Description |
|---|---|---|
| sysDescr | `1.3.6.1.2.1.1.1.0` | Description complète du système |
| sysObjectID | `1.3.6.1.2.1.1.2.0` | Identifiant de l'équipement |
| sysUpTime | `1.3.6.1.2.1.1.3.0` | Temps depuis le dernier démarrage |
| sysContact | `1.3.6.1.2.1.1.4.0` | Contact administrateur |
| sysName | `1.3.6.1.2.1.1.5.0` | Nom de la machine |
| sysLocation | `1.3.6.1.2.1.1.6.0` | Localisation physique |
| sysServices | `1.3.6.1.2.1.1.7.0` | Services actifs (entier) |

---

## Bug rencontré et résolution

### Problème

snmpd ne démarrait pas avec l'erreur :
```
Error opening specified endpoint "udp:161"
```

### Cause

Ubuntu 20.04 inclut dans `/etc/snmp/snmpd.conf` une directive en minuscules :
```
agentaddress  127.0.0.1,[::1]
```

Le module `lineinfile` d'Ansible utilisant un regexp sensible à la casse (`^agentAddress`) ne remplaçait pas cette ligne — les deux directives coexistaient et snmpd refusait de démarrer.

### Solution

Utiliser deux tasks distinctes — supprimer avant d'insérer — avec un regexp insensible à la casse :

```yaml
- name: Supprimer toute directive agentAddress existante
  lineinfile:
    path: /etc/snmp/snmpd.conf
    regexp: '^[aA]gent[aA]ddress'
    state: absent

- name: Ajouter agentAddress correct
  lineinfile:
    path: /etc/snmp/snmpd.conf
    line: 'agentAddress udp:0.0.0.0:161'
```

### Leçon retenue

`lineinfile` avec `regexp` + `line` remplace la première ligne correspondante mais ne supprime pas les autres occurrences avec une casse différente. Pour toute modification de configuration critique, privilégier `state: absent` suivi d'une insertion propre.

---

## Compétences mobilisées

- Vagrant — provisioning de VM reproductible
- Ansible (`ansible_local`) — configuration as code sur Windows sans Ansible natif
- SNMP v2c — protocole de supervision réseau, MIB, OID, communauté
- Debug méthodique — `systemctl`, `journalctl`, `ss`, `grep` pour isoler la cause racine
- iReasoning MIB Browser — exploration graphique d'une MIB depuis Windows