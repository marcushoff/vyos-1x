#!/usr/bin/env python3
#
# Copyright (C) 2020 echo reply maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import os

from copy import deepcopy
from json import dump

from vyos import ConfigError
from vyos.config import Config
from vyos.util import call, cmd, chown, chmod_750

CONFIG_FILE = r'/var/lib/zerotier-one/local.conf'
AUTH_DIR = r'/config/auth'
MOON_DIR = r'/var/lib/zerotier-one/moons.d'

default_config_data = {
    'local': {
        'physical': {},
        'virtual': {},
        'settings': {
            'portMappingEnabled': True,
            'allowSecondaryPort': True,
            'softwareUpdate': 'disable',
            'softwareUpdateChannel': 'release',
            'interfacePrefixBlacklist': [],
            'allowTcpFallbackRelay': True,
            'multipathMode': 0
        }
    },
    'moon_files': [],
    'moon':[],
    'moons_changed': False
}

def _migrate_moon(file):
    if not os.path.exists(f'{AUTH_DIR}/{file}'):
        raise ConfigError(f'Cannot find file "{AUTH_DIR}/{file}"!')

    os.rename(f'{AUTH_DIR}/{file}', f'{MOON_DIR}/{file}')

def get_config():
    zerotier = deepcopy(default_config_data)
    conf = Config()
    base = 'vpn zerotier'
    if not conf.exists(base):
        return None
    conf.set_level(base)
    local = zerotier['local']

    if conf.exists('physical'):
        for node in conf.list_nodes('physical'):
            conf.set_level(base + f' physical {node}')
            physical = {
                'blacklist': False,
                'trustedPathId': 0,
                'mtu': 0
            }

            if conf.exists('blacklist'):
                physical['blacklist'] = True
            if conf.exists('trusted-path-id'):
                physical['trustedPathId'] = int(conf.return_value(['trusted-path-id']))
            if conf.exists('mtu'):
                physical['mtu'] = int(conf.return_value(['mtu']))

            local['physical'][node] = physical
        conf.set_level(base)

    if conf.exists('virtual'):
        for node in conf.list_nodes('virtual'):
            conf.set_level(base + f' virtual {node}')
            virtual = {
                'try': [],
                'blacklist': []
            }

            if conf.exists('try address'):
                for address in conf.list_nodes('try address'):
                    ports = conf.return_values([f'try address {address} port'])
                    for port in ports:
                        virtual['try'].append(address + '/' + port)
                    if len(ports) == 0:
                        virtual['try'].append(address)
            if conf.exists('blacklist path'):
                virtual['blacklist'] = conf.return_values(['blacklist path'])

            local['virtual'][node] = virtual
        conf.set_level(base)

    if conf.exists('port'):
        conf.set_level(base + ' port')
        if conf.exists('primary'):
            local['settings']['primaryPort'] = int(conf.return_value(['primary']))
        if conf.exists('secondary'):
            local['settings']['secondaryPort'] = int(conf.return_value(['secondary']))
        if conf.exists('tertiary'):
            local['settings']['tertiaryPort'] = int(conf.return_value(['tertiary']))
        if conf.exists('only-primary'):
            local['settings']['allowSecondaryPort'] = False
        if conf.exists('no-mapping'):
            local['settings']['portMappingEnabled'] = False
        conf.set_level(base)

    if conf.exists('blacklist'):
        local['settings']['interfacePrefixBlacklist'] = conf.return_values(['blacklist interface'])

    if conf.exists('no-fallback-relay'):
        local['settings']['allowTcpFallbackRelay'] = False

    if conf.exists('multipath-mode'):
        mapping = {
            'none': 0,
            'random': 1,
            'proportional': 2
        }
        local['settings']['multipathMode'] = mapping[conf.return_value(['multipath-mode'])]

    if conf.exists('moon file'):
        for file in conf.list_nodes('moon file'):
            zerotier['moon_files'].append(file)

    if conf.exists('moon id'):
        for wid in conf.list_nodes('moon id'):
            if conf.exists(f'moon id {wid} root'):
                for root in conf.list_nodes(f'moon id {wid} root'):
                    zerotier['moon'].append({wid, root})
            else:
                zerotier['moon'].append({wid, None})
# TODO: make list of moons we have left
    return zerotier

def verify(zerotier):
    # bail out early - looks like removal from running config
    if zerotier is None:
        return None

    local = zerotier['local']
    # Physical blacklist cannot coexist with other settings
    phy = local['physical']
    for key in phy:
        if phy[key]['blacklist'] and (phy[key]['trustedPathId'] or phy[key]['mtu']):
            raise ConfigError(
                f'ZeroTier blacklist for physical "{phy[key]}" is incompatible '
                f'with other settings!')

    # A virtual try address requires a least one port
    virtual = local['virtual']
    for key in virtual:
        if not all('/' in t for t in virtual[key]['try']):
            raise ConfigError(
                f'ZeroTier virtual "{key}" try, requires at least 1 port!')

    for wid, root in zerotier['moon']:
        if not root:
            raise ConfigError(
                f'ZeroTier moon with world ID "{wid}", requires at least 1 '
                f'root!')

    return True

def generate(zerotier):
    # bail out early - looks like removal from running config
    if zerotier is None:
        return None

    with open(CONFIG_FILE, 'w') as file:
        dump(zerotier['local'], file, indent=4)

    # create moon.d if it doesn't exist
    if not os.path.exists(MOON_DIR):
        os.makedirs(MOON_DIR)
        chown(MOON_DIR, 'zerotier-one', 'zerotier-one')
        chmod_750(MOON_DIR)

    # grab all files in moon directory
    files = [f for f in os.listdir(MOON_DIR) if os.path.isfile(os.path.join(MOON_DIR, f))]
    # grab all files not in config
    remove = [f for f in files if f not in zerotier['moon_files']]
    for file in remove:
        os.remove(f'{MOON_DIR}/{file}')
        zerotier['moons_changed'] = True

    # grab all files not in directory
    add = [f for f in zerotier['moon_files'] if f not in files]
    for file in add:
        _migrate_moon(file)
        zerotier['moons_changed'] = True

    return None

def apply(zerotier):
    if zerotier['moons_changed']:
        # NOTE: this might happen twice, since we also do it in the interfaces file
        cmd('systemctl restart zerotier-one.service')

    cmd('systemctl start zerotier-one.service')

# TODO: deorbit moons we have left
    for wid, root in zerotier['moon']:
        cmd(f'sudo zerotier-cli orbit {wid} {root}')

    return None

if __name__ == '__main__':
    try:
        config = get_config()
        verify(config)
        generate(config)
        apply(config)
    except ConfigError as error:
        print(error)
        sys.exit(1)
