# Tests de Validation — Séance SNMP (TP1 à TP4)

## Comment utiliser ce fichier

Chaque test indique :
- **Contexte** : où et comment lancer la commande
- **Commande** : ce qu'on exécute
- **Résultat attendu** : ce qu'on doit voir
- **Statut** : ✅ OK / ❌ KO / ⚠️ Warning acceptable

---

## TP1 — Agent Linux + iReasoning

### 1.1 Validation du provisioning Ansible

**Contexte** : PowerShell, dossier `D:\Seance1-SNMP\`

```powershell
vagrant destroy -f && vagrant up
```

**Résultat attendu** :
```
PLAY RECAP
default : ok=9   changed=8   unreachable=0   failed=0
```

| Critère | Attendu | Statut |
|---|---|---|
| `failed` | 0 | |
| `unreachable` | 0 | |
| `ok` | ≥ 9 | |
| snmpd démarré | `Active: active (running)` | |

---

### 1.2 Validation fonctionnelle — snmpd écoute

**Contexte** : VM (`vagrant ssh`)

```bash
sudo ss -ulnp | grep 161
```

**Résultat attendu** :
```
UNCONN 0 0 0.0.0.0:161 0.0.0.0:* users:(("snmpd",...))
```

| Critère | Attendu | Statut |
|---|---|---|
| Port 161 UDP ouvert | `0.0.0.0:161` | |
| Process écoutant | `snmpd` | |

---

### 1.3 Validation fonctionnelle — sysName et sysUpTime en CLI

**Contexte** : VM (`vagrant ssh`)

```bash
snmpget -v2c -c public 127.0.0.1 1.3.6.1.2.1.1.5.0
snmpget -v2c -c public 127.0.0.1 1.3.6.1.2.1.1.3.0
```

**Résultat attendu** :
```
iso.3.6.1.2.1.1.5.0 = STRING: "ubuntu-focal"
iso.3.6.1.2.1.1.3.0 = Timeticks: (...) 0:XX:XX.XX
```

| Critère | Attendu | Statut |
|---|---|---|
| sysName retourné | `ubuntu-focal` | |
| sysUpTime retourné | Timeticks > 0 | |
| Pas de timeout | Pas de `No Response` | |

---

### 1.4 Validation fonctionnelle — iReasoning MIB Browser

**Contexte** : Windows, iReasoning ouvert

Configuration :
- Address : `192.168.56.10`
- Port : `161`
- Community : `public`
- Version : `2`

```
OID : .1.3.6.1.2.1.1.5.0 → Get
OID : .1.3.6.1.2.1.1.3.0 → Get
```

| Critère | Attendu | Statut |
|---|---|---|
| Connexion établie | Pas de timeout | |
| sysName affiché | `ubuntu-focal` | |
| sysUpTime affiché | Valeur TimeTicks | |

---

## TP2 — Mono-machine Linux CLI

### 2.1 Validation du provisioning Ansible

**Contexte** : PowerShell, dossier `D:\Seance1-SNMP\`

```powershell
vagrant destroy -f && vagrant up
```

**Résultat attendu** :
```
PLAY RECAP
default : ok=9   changed=8   unreachable=0   failed=0
```

| Critère | Attendu | Statut |
|---|---|---|
| `failed` | 0 | |
| Vues HOST-RESOURCES-MIB ajoutées | Task `changed` | |
| Vues UCD-SNMP-MIB ajoutées | Task `changed` | |

---

### 2.2 Validation fonctionnelle — RAM totale

**Contexte** : VM (`vagrant ssh`)

```bash
snmpget -v2c -c public localhost 1.3.6.1.2.1.25.2.2.0
```

**Résultat attendu** :
```
iso.3.6.1.2.1.25.2.2.0 = INTEGER: 987984
```

| Critère | Attendu | Statut |
|---|---|---|
| Valeur retournée | INTEGER > 0 | |
| Pas de `No Such Object` | OID accessible | |

---

### 2.3 Validation fonctionnelle — RAM utilisée

**Contexte** : VM (`vagrant ssh`)

```bash
snmpget -v2c -c public localhost 1.3.6.1.2.1.25.2.3.1.5.1
snmpget -v2c -c public localhost 1.3.6.1.2.1.25.2.3.1.6.1
echo "scale=2; $(snmpget -v2c -c public localhost 1.3.6.1.2.1.25.2.3.1.6.1 | awk '{print $NF}') * 100 / $(snmpget -v2c -c public localhost 1.3.6.1.2.1.25.2.3.1.5.1 | awk '{print $NF}')" | bc
```

**Résultat attendu** :
```
Pourcentage entre 0 et 100
```

| Critère | Attendu | Statut |
|---|---|---|
| hrStorageSize retourné | INTEGER > 0 | |
| hrStorageUsed retourné | INTEGER > 0 | |
| Pourcentage calculable | Entre 0 et 100 | |

---

### 2.4 Validation fonctionnelle — Load average

**Contexte** : VM (`vagrant ssh`)

```bash
snmpget -v2c -c public localhost 1.3.6.1.4.1.2021.10.1.3.1
snmpget -v2c -c public localhost 1.3.6.1.4.1.2021.10.1.3.2
snmpget -v2c -c public localhost 1.3.6.1.4.1.2021.10.1.3.3
```

**Résultat attendu** :
```
iso.3.6.1.4.1.2021.10.1.3.1 = STRING: "0.XX"
iso.3.6.1.4.1.2021.10.1.3.2 = STRING: "0.XX"
iso.3.6.1.4.1.2021.10.1.3.3 = STRING: "0.XX"
```

| Critère | Attendu | Statut |
|---|---|---|
| Load avg 1 min retourné | STRING numérique | |
| Load avg 5 min retourné | STRING numérique | |
| Load avg 15 min retourné | STRING numérique | |
| Pas de `No Such Object` | OIDs accessibles | |

---

## TP3 — Architecture Distante + Traps

### 3.1 Validation du provisioning Ansible

**Contexte** : PowerShell, dossier `D:\Seance1-SNMP-TP3\`

```powershell
vagrant destroy -f && vagrant up
```

**Résultat attendu** :
```
manager : ok=11  changed=8   unreachable=0   failed=0
agent   : ok=14  changed=13  unreachable=0   failed=0
```

| Critère | Attendu | Statut |
|---|---|---|
| manager `failed` | 0 | |
| agent `failed` | 0 | |
| snmptrapd démarré (manager) | `Active: active (running)` | |
| snmpd démarré (agent) | `Active: active (running)` | |

---

### 3.2 Validation fonctionnelle — Connectivité réseau

**Contexte** : manager (`vagrant ssh manager`)

```bash
ping -c 3 192.168.56.20
```

**Résultat attendu** :
```
3 packets transmitted, 3 received, 0% packet loss
```

| Critère | Attendu | Statut |
|---|---|---|
| Perte de paquets | 0% | |
| RTT | < 5ms | |

---

### 3.3 Validation fonctionnelle — Supervision distante IF-MIB

**Contexte** : manager (`vagrant ssh manager`)

```bash
snmpwalk -v2c -c supervision 192.168.56.20 IF-MIB::ifDescr
snmpwalk -v2c -c supervision 192.168.56.20 IF-MIB::ifOperStatus
```

**Résultat attendu** :
```
IF-MIB::ifDescr.1 = STRING: lo
IF-MIB::ifDescr.2 = STRING: Intel Corporation 82540EM ...
IF-MIB::ifDescr.3 = STRING: Intel Corporation 82540EM ...
IF-MIB::ifOperStatus.1 = INTEGER: up(1)
IF-MIB::ifOperStatus.2 = INTEGER: up(1)
IF-MIB::ifOperStatus.3 = INTEGER: up(1)
```

| Critère | Attendu | Statut |
|---|---|---|
| 3 interfaces détectées | ifDescr.1, .2, .3 | |
| Toutes up | `up(1)` | |
| Pas de `Unknown Object` | MIBs chargées | |

---

### 3.4 Validation fonctionnelle — snmpset depuis le manager

**Contexte** : manager (`vagrant ssh manager`)

```bash
snmpset -v2c -c admin 192.168.56.20 SNMPv2-MIB::sysContact.0 s "admin@test.lab"
snmpget -v2c -c supervision 192.168.56.20 SNMPv2-MIB::sysContact.0
```

**Résultat attendu** :
```
SNMPv2-MIB::sysContact.0 = STRING: admin@test.lab
```

| Critère | Attendu | Statut |
|---|---|---|
| snmpset accepté | Pas de `notWritable` | |
| Valeur persistée | `admin@test.lab` retourné | |

---

### 3.5 Validation des traps — coldStart

**Contexte** : manager (`vagrant ssh manager`) — surveiller le log

```bash
sudo tail -f /var/log/snmptrapd.log
```

**Contexte** : PowerShell — redémarrer l'agent

```powershell
vagrant reload agent
```

**Résultat attendu dans le log** :
```
[UDP: [192.168.56.20]:XXXXX->[192.168.56.10]:162]:
iso.3.6.1.2.1.1.3.0 = Timeticks: (...) 0:00:00.XX
iso.3.6.1.6.3.1.1.4.1.0 = OID: iso.3.6.1.6.3.1.1.5.1
```

| Critère | Attendu | Statut |
|---|---|---|
| Trap reçue après reload | Nouvelle ligne dans le log | |
| Source | `192.168.56.20` | |
| OID trap | `iso.3.6.1.6.3.1.1.5.1` (coldStart) | |
| Uptime | Timeticks faible (< 1 min) | |

---

### 3.6 Validation des traps — linkDown

**Contexte** : agent (`vagrant ssh agent`)

```bash
sudo bash -c 'ip link set enp0s3 down; sleep 10; ip link set enp0s3 up' &
```

**Contexte** : manager — surveiller le log (attendre jusqu'à 60 secondes)

```bash
sudo tail -f /var/log/snmptrapd.log
```

**Résultat attendu** :
```
[UDP: [192.168.56.20]:XXXXX->[192.168.56.10]:162]:
iso.3.6.1.6.3.1.1.4.1.0 = OID: iso.3.6.1.6.3.1.1.5.1
```

| Critère | Attendu | Statut |
|---|---|---|
| Trap reçue dans les 60s | Nouvelle ligne dans le log | |
| Source | `192.168.56.20` | |
| Délai de détection | < 60 secondes | |

---

## TP4 — SNMPv3 authPriv

### 4.1 Validation du provisioning Ansible

**Contexte** : PowerShell, dossier `D:\Seance1-SNMP-TP4\`

```powershell
vagrant destroy -f && vagrant up
```

**Résultat attendu** :
```
manager : ok=11  changed=8   unreachable=0   failed=0
agent   : ok=15  changed=14  unreachable=0   failed=0
```

| Critère | Attendu | Statut |
|---|---|---|
| manager `failed` | 0 | |
| agent `failed` | 0 | |
| Task `Créer l'utilisateur SNMPv3` | `changed` | |
| Task `Marquer l'utilisateur` | `changed` | |

---

### 4.2 Validation du provisioning — utilisateur SNMPv3 créé

**Contexte** : agent (`vagrant ssh agent`)

```bash
sudo grep -i "usmUser\|admin_sec" /var/lib/snmp/snmpd.conf
```

**Résultat attendu** :
```
usmUser 1 3 0x80001f88... 0x61646d696e5f736563 ...
```

| Critère | Attendu | Statut |
|---|---|---|
| Entrée `usmUser` présente | Ligne commençant par `usmUser` | |
| `admin_sec` en hex | `0x61646d696e5f736563` | |
| Fichier marqueur | `/var/lib/snmp/.admin_sec_created` existe | |

---

### 4.3 Validation fonctionnelle — SNMPv3 authPriv

**Contexte** : manager (`vagrant ssh manager`)

```bash
snmpget -v3 -u admin_sec -l authPriv \
  -a SHA -A PassAuth123 \
  -x AES -X PassPriv123 \
  192.168.56.20 SNMPv2-MIB::sysName.0
```

**Résultat attendu** :
```
SNMPv2-MIB::sysName.0 = STRING: snmp-agent
```

| Critère | Attendu | Statut |
|---|---|---|
| Réponse reçue | `snmp-agent` | |
| Pas de `Unknown user name` | Utilisateur reconnu | |
| Pas de `Authentication failure` | Mot de passe correct | |

---

### 4.4 Validation de la sécurité — niveaux de sécurité

**Contexte** : manager (`vagrant ssh manager`)

```bash
# noAuthNoPriv — doit être refusé
snmpget -v3 -u admin_sec -l noAuthNoPriv \
  192.168.56.20 SNMPv2-MIB::sysName.0

# authNoPriv — doit être accepté
snmpget -v3 -u admin_sec -l authNoPriv \
  -a SHA -A PassAuth123 \
  192.168.56.20 SNMPv2-MIB::sysName.0

# authPriv — doit être accepté
snmpget -v3 -u admin_sec -l authPriv \
  -a SHA -A PassAuth123 \
  -x AES -X PassPriv123 \
  192.168.56.20 SNMPv2-MIB::sysName.0
```

| Niveau | Résultat attendu | Statut |
|---|---|---|
| `noAuthNoPriv` | `authorizationError` | |
| `authNoPriv` | `snmp-agent` retourné | |
| `authPriv` | `snmp-agent` retourné | |

---

### 4.5 Validation de la sécurité — mauvais mot de passe

**Contexte** : manager (`vagrant ssh manager`)

```bash
snmpget -v3 -u admin_sec -l authPriv \
  -a SHA -A MauvaisMotDePasse \
  -x AES -X PassPriv123 \
  192.168.56.20 SNMPv2-MIB::sysName.0
```

**Résultat attendu** :
```
snmpget: Authentication failure (incorrect password, community or key)
```

| Critère | Attendu | Statut |
|---|---|---|
| Accès refusé | `Authentication failure` | |
| Pas de données retournées | Aucune valeur | |

---

### 4.6 Validation de la sécurité — utilisateur inexistant

**Contexte** : manager (`vagrant ssh manager`)

```bash
snmpget -v3 -u utilisateur_bidon -l authPriv \
  -a SHA -A PassAuth123 \
  -x AES -X PassPriv123 \
  192.168.56.20 SNMPv2-MIB::sysName.0
```

**Résultat attendu** :
```
snmpget: Unknown user name
```

| Critère | Attendu | Statut |
|---|---|---|
| Accès refusé | `Unknown user name` | |

---

### 4.7 Validation de la sécurité — analyse de trames

**Contexte** : manager (`vagrant ssh manager`)

```bash
# Lancer la capture
sudo tcpdump -i enp0s8 -w /tmp/validation_capture.pcap port 161 &

# Requête SNMPv3
snmpget -v3 -u admin_sec -l authPriv \
  -a SHA -A PassAuth123 -x AES -X PassPriv123 \
  192.168.56.20 SNMPv2-MIB::sysName.0

# Arrêter la capture
sudo pkill tcpdump

# Analyser
tshark -r /tmp/validation_capture.pcap -Y snmp -T fields \
  -e snmp.msgVersion \
  -e snmp.msgFlags.priv \
  -e snmp.msgFlags.auth \
  -e snmp.msgUserName
```

**Résultat attendu** :
```
3    0    0          (discovery — non chiffré)
3    0    0          (report engineID)
3    1    1    admin_sec   (requête chiffrée)
3    1    1    admin_sec   (réponse chiffrée)
```

| Critère | Attendu | Statut |
|---|---|---|
| Version SNMPv3 | `msgVersion = 3` | |
| Chiffrement actif | `msgFlags.priv = 1` | |
| Authentification active | `msgFlags.auth = 1` | |
| PDU illisible | `encryptedPDU` dans tshark | |

---

## Matrice de validation globale

| Test | TP | Catégorie | Statut |
|---|---|---|---|
| 1.1 Provisioning Ansible | TP1 | Provisioning | |
| 1.2 snmpd écoute port 161 | TP1 | Fonctionnel | |
| 1.3 sysName et sysUpTime CLI | TP1 | Fonctionnel | |
| 1.4 iReasoning MIB Browser | TP1 | Fonctionnel | |
| 2.1 Provisioning Ansible | TP2 | Provisioning | |
| 2.2 RAM totale | TP2 | Fonctionnel | |
| 2.3 RAM utilisée | TP2 | Fonctionnel | |
| 2.4 Load average | TP2 | Fonctionnel | |
| 3.1 Provisioning Ansible | TP3 | Provisioning | |
| 3.2 Connectivité réseau | TP3 | Fonctionnel | |
| 3.3 IF-MIB distante | TP3 | Fonctionnel | |
| 3.4 snmpset | TP3 | Fonctionnel | |
| 3.5 Trap coldStart | TP3 | Traps | |
| 3.6 Trap linkDown | TP3 | Traps | |
| 4.1 Provisioning Ansible | TP4 | Provisioning | |
| 4.2 Utilisateur SNMPv3 créé | TP4 | Provisioning | |
| 4.3 SNMPv3 authPriv | TP4 | Fonctionnel | |
| 4.4 Niveaux de sécurité | TP4 | Sécurité | |
| 4.5 Mauvais mot de passe | TP4 | Sécurité | |
| 4.6 Utilisateur inexistant | TP4 | Sécurité | |
| 4.7 Analyse de trames | TP4 | Sécurité | |

---

## Warnings attendus et acceptables

Ces messages apparaissent systématiquement et n'indiquent pas une erreur :

| Message | Source | Impact |
|---|---|---|
| `Bad operator (INTEGER): At line 73 in SNMPv2-PDU` | Bug paquet Ubuntu 20.04 | Aucun — ignorer |
| `The guest additions on this VM do not match` | VirtualBox version mismatch | Aucun sur ce lab |
| `Cannot adopt OID in UCD-SNMP-MIB` | MIBs partielles sans SNMPv2-SMI | Aucun — ignorer |
| `NET-SNMP version 5.8 AgentX subagent connected` | Log snmptrapd au démarrage | Aucun — normal |