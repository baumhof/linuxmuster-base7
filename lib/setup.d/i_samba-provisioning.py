#!/usr/bin/python3
#
# samba provisioning
# thomas@linuxmuster.net
# 20180209
#

import configparser
import constants
import glob
import os
import sys
from functions import randomPassword
from functions import replaceInFile
from functions import printScript
from functions import subProc

title = os.path.basename(__file__).replace('.py', '').split('_')[1]
logfile = constants.LOGDIR + '/setup.' + title + '.log'

printScript('', 'begin')
printScript(title)

# stop services
msg = 'Stopping samba services '
printScript(msg, '', False, False, True)
services = ['winbind', 'samba-ad-dc', 'smbd', 'nmbd']
try:
    for s in services:
        subProc('service ' + s + ' stop', logfile)
    printScript(' Success!', '', True, True, False, len(msg))
except:
    printScript(' Failed!', '', True, True, False, len(msg))
    sys.exit(1)

# read setup ini
msg = 'Reading setup data '
printScript(msg, '', False, False, True)
setupini = constants.SETUPINI
try:
    setup = configparser.ConfigParser(inline_comment_prefixes=('#', ';'))
    setup.read(setupini)
    realm = setup.get('setup', 'domainname').upper()
    sambadomain = setup.get('setup', 'sambadomain')
    firewallip = setup.get('setup', 'firewallip')
    domainname = setup.get('setup', 'domainname')
    basedn = setup.get('setup', 'basedn')
    printScript(' Success!', '', True, True, False, len(msg))
except:
    printScript(' Failed!', '', True, True, False, len(msg))
    sys.exit(1)

# generate ad admin password
msg = 'Generating AD admin password '
printScript(msg, '', False, False, True)
try:
    adadminpw = randomPassword(16)
    with open(constants.ADADMINSECRET, 'w') as secret:
        secret.write(adadminpw)
    subProc('chmod 600 ' + constants.ADADMINSECRET, logfile)
    # symlink for sophomorix
    subProc('ln -sf ' + constants.ADADMINSECRET + ' ' + constants.SOPHOSYSDIR + '/sophomorix-samba.secret', logfile)
    printScript(' Success!', '', True, True, False, len(msg))
except:
    printScript(' Failed!', '', True, True, False, len(msg))
    sys.exit(1)

# alte smb.conf löschen
smbconf = '/etc/samba/smb.conf'
if os.path.isfile(smbconf):
    os.unlink(smbconf)

# provisioning samba
msg = 'Provisioning samba '
printScript(msg, '', False, False, True)
try:
    subProc('samba-tool domain provision --use-rfc2307 --server-role=dc --domain=' + sambadomain + ' --realm=' + realm + ' --adminpass=' + adadminpw, logfile)
    printScript(' Success!', '', True, True, False, len(msg))
except:
    printScript(' Failed!', '', True, True, False, len(msg))
    sys.exit(1)

# create krb5.conf symlink
msg = 'Provisioning krb5 '
printScript(msg, '', False, False, True)
try:
    krb5conf_src = '/var/lib/samba/private/krb5.conf'
    krb5conf_dst = '/etc/krb5.conf'
    if os.path.isfile(krb5conf_dst):
        os.remove(krb5conf_dst)
        os.symlink(krb5conf_src, krb5conf_dst)
        k = configparser.ConfigParser(inline_comment_prefixes=('#', ';'))
        k.read(krb5conf_dst)
        k.set('libdefaults', 'dns_lookup_realm', 'true')
        with open(krb5conf_dst, 'w') as config:
            k.write(config)
    printScript(' Success!', '', True, True, False, len(msg))
except:
    printScript(' Failed!', '', True, True, False, len(msg))
    sys.exit(1)

# set dns forwarder & global options
msg = 'Updating smb.conf with global options '
printScript(msg, '', False, False, True)
try:
    samba = configparser.ConfigParser(inline_comment_prefixes=('#', ';'))
    samba.read(smbconf)
    samba.set('global', 'dns forwarder', firewallip)
    samba.set('global', 'idmap config * : range', '10000-99999')
    samba.set('global', 'registry shares', 'yes')
    samba.set('global', 'host msdfs', 'yes')
    samba.set('global', 'tls enabled', 'yes')
    samba.set('global', 'tls keyfile', constants.SSLDIR + '/server.key.pem')
    samba.set('global', 'tls certfile', constants.SSLDIR + '/server.cert.pem')
    samba.set('global', 'tls cafile', constants.CACERT)
    samba.set('global', 'tls verify peer', 'ca_and_name')
    samba.set('global', 'ldap server require strong auth', 'no')
    with open (smbconf, 'w') as outfile:
        samba.write(outfile)
    printScript(' Success!', '', True, True, False, len(msg))
except:
    printScript(' Failed!', '', True, True, False, len(msg))
    sys.exit(1)

# repair smb.conf's idmap option
replaceInFile(smbconf, 'idmap_ldb = use rfc2307 = yes', 'idmap_ldb:use rfc2307 = yes')

# restart services
msg = 'Restarting samba services '
printScript(msg, '', False, False, True)
try:
    subProc('systemctl daemon-reload', logfile)
    for s in services:
        subProc('systemctl stop ' + s, logfile)
    # start only samba-ad-dc service
    subProc('systemctl unmask samba-ad-dc.service', logfile)
    subProc('systemctl enable samba-ad-dc.service', logfile)
    printScript(' Success!', '', True, True, False, len(msg))
except:
    printScript(' Failed!', '', True, True, False, len(msg))
    sys.exit(1)

# backup samba before sophomorix modifies anything
msg = 'Backing up samba '
printScript(msg, '', False, False, True)
try:
    #subProc('sophomorix-samba --schema-load', logfile)
    subProc('sophomorix-samba --backup-samba without-sophomorix-schema', logfile)
    printScript(' Success!', '', True, True, False, len(msg))
except:
    printScript(' Failed!', '', True, True, False, len(msg))
    sys.exit(1)

# loading sophomorix samba schema
msg = 'Provisioning sophomorix samba schema '
printScript(msg, '', False, False, True)
try:
    #subProc('sophomorix-samba --schema-load', logfile)
    subProc('cd /usr/share/sophomorix/schema ; ./sophomorix_schema_add.sh ' + basedn + ' . -H /var/lib/samba/private/sam.ldb -writechanges', logfile)
    subProc('systemctl start samba-ad-dc.service', logfile)
    printScript(' Success!', '', True, True, False, len(msg))
except:
    printScript(' Failed!', '', True, True, False, len(msg))
    sys.exit(1)
