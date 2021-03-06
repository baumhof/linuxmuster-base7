#!/usr/bin/python3
#
# process config templates
# thomas@linuxmuster.net
# 20180130
#

import configparser
import constants
import datetime
import os
import sys

from functions import setupComment
from functions import backupCfg
from functions import printScript
from functions import replaceInFile
from functions import subProc

title = os.path.basename(__file__).replace('.py', '').split('_')[1]
logfile = constants.LOGDIR + '/setup.' + title + '.log'

printScript('', 'begin')
printScript(title)

# read setup data
msg = 'Reading setup data '
printScript(msg, '', False, False, True)
setupini = constants.SETUPINI
try:
    # setupdefaults.ini
    defaults = configparser.ConfigParser(inline_comment_prefixes=('#', ';'))
    defaults.read(constants.DEFAULTSINI)
    # setup.ini
    setup = configparser.ConfigParser(inline_comment_prefixes=('#', ';'))
    setup.read(setupini)
    # interface to use
    iface = setup.get('setup', 'iface')
    serverip = setup.get('setup', 'serverip')
    firewallip = setup.get('setup', 'firewallip')
    printScript(' Success!', '', True, True, False, len(msg))
except:
    printScript(' Failed!', '', True, True, False, len(msg))
    sys.exit(1)

# stop network interface
subProc('ifconfig ' + iface + ' 0.0.0.0 down', logfile)

# templates, whose corresponding configfiles must not be overwritten
do_not_overwrite = 'dhcpd.custom.conf'
# templates, whose corresponding configfiles must not be backed up
do_not_backup = [ 'interfaces.linuxmuster', 'dovecot.linuxmuster.conf', 'smb.conf']

printScript('Processing config templates:')
for f in os.listdir(constants.TPLDIR):
    source = constants.TPLDIR + '/' + f
    msg = ' * ' + f + ' '
    printScript(msg, '', False, False, True)
    try:
        with open(source, 'r') as infile:
            firstline = infile.readline().rstrip('\n')
            infile.seek(0)
            filedata = infile.read()
            # get target path
            target = firstline.partition(' ')[2]
        # do not overwrite specified configfiles if they exist
        if (f in do_not_overwrite and os.path.isfile(target)):
            printScript(' Success!', '', True, True, False, len(msg))
            continue
        for value in defaults.options('setup'):
            placeholder = '@@' + value + '@@'
            if placeholder in filedata:
                filedata = filedata.replace(placeholder, setup.get('setup', value))
        # set LINBODIR
        if '@@linbodir@@' in filedata:
            filedata = filedata.replace('@@linbodir@@', constants.LINBODIR)
        # backup file
        if f not in do_not_backup:
            backupCfg(target)
        with open(target, 'w') as outfile:
            outfile.write(setupComment())
            outfile.write(filedata)
        printScript(' Success!', '', True, True, False, len(msg))
    except:
        printScript(' Failed!', '', True, True, False, len(msg))
        sys.exit(1)

# restart network interface
msg = 'Restarting network '
printScript(msg, '', False, False, True)
try:
    subProc('service networking restart', logfile)
    printScript(' Success!', '', True, True, False, len(msg))
except:
    printScript(' Failed!', '', True, True, False, len(msg))
    sys.exit(1)

# set server time
msg = 'Adjusting server time '
printScript(msg, '', False, False, True)
subProc('service ntp stop', logfile)
subProc('ntpdate pool.ntp.org', logfile)
subProc('service ntp start', logfile)
now = str(datetime.datetime.now()).split('.')[0]
printScript(' ' + now, '', True, True, False, len(msg))
