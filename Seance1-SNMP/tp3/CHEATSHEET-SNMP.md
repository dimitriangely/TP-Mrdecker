# Cheatsheet SNMP — net-snmp

## Syntaxe générale

```
snmp<commande> -v <version> -c <communauté> <cible> <OID>
```

| Paramètre | Valeurs | Description |
|---|---|---|
| `-v` | `1`, `2c`, `3` | Version SNMP |
| `-c` | `public`, `supervision`... | Communauté |
| cible | IP ou hostname | Agent à interroger |
| OID | numérique ou symbolique | Objet à lire/modifier |

---

## snmpget — Lire une valeur précise

```bash
# Par OID numérique
snmpget -v2c -c public 192.168.56.20 1.3.6.1.2.1.1.5.0

# Par nom symbolique
snmpget -v2c -c public 192.168.56.20 SNMPv2-MIB::sysName.0
snmpget -v2c -c public 192.168.56.20 SNMPv2-MIB::sysUpTime.0
snmpget -v2c -c public 192.168.56.20 SNMPv2-MIB::sysContact.0

# RAM totale
snmpget -v2c -c public 192.168.56.20 1.3.6.1.2.1.25.2.2.0

# Load average 1 min
snmpget -v2c -c public 192.168.56.20 1.3.6.1.4.1.2021.10.1.3.1
```

---

## snmpwalk — Parcourir une branche

```bash
# Branche system complète
snmpwalk -v2c -c public 192.168.56.20 system

# Interfaces réseau
snmpwalk -v2c -c supervision 192.168.56.20 IF-MIB::ifDescr
snmpwalk -v2c -c supervision 192.168.56.20 IF-MIB::ifOperStatus

# Stockage et mémoire
snmpwalk -v2c -c public 192.168.56.20 1.3.6.1.2.1.25.2.3

# HOST-RESOURCES-MIB complète
snmpwalk -v2c -c public 192.168.56.20 .1.3.6.1.2.1.25
```

---

## snmptranslate — Convertir noms et OIDs

```bash
# Nom symbolique → OID numérique
snmptranslate -On IF-MIB::ifDescr
snmptranslate -On SNMPv2-MIB::sysName.0

# OID numérique → nom symbolique + description complète
snmptranslate -Td 1.3.6.1.2.1.2.2.1.2
snmptranslate -Td 1.3.6.1.2.1.1.5.0

# Description complète d'un OID nommé
snmptranslate -Td IF-MIB::ifOperStatus
snmptranslate -Td HOST-RESOURCES-MIB::hrMemorySize
```

---

## snmpset — Modifier une valeur

```bash
# Syntaxe : snmpset -v2c -c <communauté_rw> <cible> <OID> <type> <valeur>
snmpset -v2c -c admin 192.168.56.20 SNMPv2-MIB::sysContact.0 s "admin@lab.fr"
snmpset -v2c -c admin 192.168.56.20 SNMPv2-MIB::sysLocation.0 s "Datacenter-Paris"
```

Types de valeurs :

| Type | Lettre | Exemple |
|---|---|---|
| String | `s` | `s "valeur"` |
| Integer | `i` | `i 42` |
| TimeTicks | `t` | `t 0` |
| IP Address | `a` | `a 192.168.1.1` |
| OID | `o` | `o 1.3.6.1.2.1.1` |

Prérequis pour `snmpset` :
- Communauté `rwcommunity` configurée sur l'agent
- OID avec `MAX-ACCESS read-write` dans la MIB
- Valeur non définie statiquement dans `snmpd.conf`

---

## snmptrap — Envoyer une trap manuellement

```bash
# Trap coldStart manuelle vers un manager
snmptrap -v2c -c supervision 192.168.56.10 '' 1.3.6.1.6.3.1.1.5.1
```

---

## OIDs fréquents

### Groupe system (MIB-2)

| Nom | OID | Description |
|---|---|---|
| sysDescr | `1.3.6.1.2.1.1.1.0` | Description OS et matériel |
| sysUpTime | `1.3.6.1.2.1.1.3.0` | Uptime depuis démarrage |
| sysContact | `1.3.6.1.2.1.1.4.0` | Contact administrateur |
| sysName | `1.3.6.1.2.1.1.5.0` | Nom de la machine |
| sysLocation | `1.3.6.1.2.1.1.6.0` | Localisation physique |

### IF-MIB — Interfaces réseau

| Nom | OID | Description |
|---|---|---|
| ifNumber | `1.3.6.1.2.1.2.1.0` | Nombre d'interfaces |
| ifDescr | `1.3.6.1.2.1.2.2.1.2` | Description de l'interface |
| ifOperStatus | `1.3.6.1.2.1.2.2.1.8` | État opérationnel (1=up, 2=down) |
| ifInOctets | `1.3.6.1.2.1.2.2.1.10` | Octets reçus |
| ifOutOctets | `1.3.6.1.2.1.2.2.1.16` | Octets émis |

### HOST-RESOURCES-MIB — Ressources système

| Nom | OID | Description |
|---|---|---|
| hrMemorySize | `1.3.6.1.2.1.25.2.2.0` | RAM totale (KB) |
| hrStorageSize | `1.3.6.1.2.1.25.2.3.1.5` | Taille stockage (KB) |
| hrStorageUsed | `1.3.6.1.2.1.25.2.3.1.6` | Stockage utilisé (KB) |

### UCD-SNMP-MIB — Load average

| Nom | OID | Description |
|---|---|---|
| laLoad (1 min) | `1.3.6.1.4.1.2021.10.1.3.1` | Load average 1 minute |
| laLoad (5 min) | `1.3.6.1.4.1.2021.10.1.3.2` | Load average 5 minutes |
| laLoad (15 min) | `1.3.6.1.4.1.2021.10.1.3.3` | Load average 15 minutes |

### Traps standard

| OID | Nom | Déclencheur |
|---|---|---|
| `1.3.6.1.6.3.1.1.5.1` | coldStart | Démarrage agent |
| `1.3.6.1.6.3.1.1.5.2` | warmStart | Redémarrage sans réinit |
| `1.3.6.1.6.3.1.1.5.3` | linkDown | Interface qui tombe |
| `1.3.6.1.6.3.1.1.5.4` | linkUp | Interface qui remonte |
| `1.3.6.1.4.1.8072.4.0.2` | nsNotifyShutdown | Arrêt snmpd |

---

## Configuration snmpd.conf — Directives clés

```
# Écouter sur toutes les interfaces
agentAddress udp:0.0.0.0:161

# Communauté read-only restreinte à une IP
rocommunity supervision 192.168.56.10

# Communauté read-write restreinte à une IP
rwcommunity admin 192.168.56.10

# Étendre la vue pour IF-MIB
view systemonly included .1.3.6.1.2.1.2

# Étendre la vue pour HOST-RESOURCES-MIB
view systemonly included .1.3.6.1.2.1.25

# Étendre la vue pour UCD-SNMP-MIB
view systemonly included .1.3.6.1.4.1.2021

# Envoyer les traps vers un manager
trap2sink 192.168.56.10 supervision

# Monitor avec trap automatique
monitor -r 60 -e linkDown "Interface down" ifOperStatus.2 != 1
```

---

## Calcul RAM utilisée

```bash
# Récupérer les valeurs
SIZE=$(snmpget -v2c -c public localhost 1.3.6.1.2.1.25.2.3.1.5.1 | awk '{print $NF}')
USED=$(snmpget -v2c -c public localhost 1.3.6.1.2.1.25.2.3.1.6.1 | awk '{print $NF}')

# Calculer le pourcentage
echo "scale=2; $USED * 100 / $SIZE" | bc
```

---

## Bugs connus Ubuntu 20.04

| Problème | Cause | Solution |
|---|---|---|
| `agentaddress` conflict | Config par défaut en minuscules | `state: absent` + réinsertion |
| `logOption` non reconnu | Token non supporté par snmptrapd 5.8 | Utiliser `-Lf` dans ExecStart |
| `snmptrapd` ignore `/etc/default/snmptrapd` | Service systemd avec ExecStart fixe | Override systemd |
| MIBs standard absentes | Raisons de licence Ubuntu | `apt install snmp-mibs-downloader` |
| `Bad operator (INTEGER) SNMPv2-PDU` | Bug fichier MIB Ubuntu | Warning bénin, ignorer |
| `sysContact`/`sysLocation` notWritable | Valeurs définies dans snmpd.conf | Supprimer les lignes statiques |