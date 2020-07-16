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
from filecmp import cmp

from vyos import ConfigError
from vyos.config import Config
from vyos.util import call, cmd, chown, chmod_755

CONFIG_FILE = r'/var/lib/zerotier-one/local.conf'
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
    'moon_remove': [],
    'moons_changed': False
}

def _migrate_moon(file):
    if not os.path.exists(file):
        raise ConfigError(f'Cannot find file "{file}"!')
    cmd(f'sudo cp {file} {MOON_DIR}/{os.path.basename(file)}')


def get_config():
    zerotier = deepcopy(default_config_data)
    conf = Config()
    base = 'vpn zerotier'
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

    conf.set_level(base)
    if conf.exists('moon file'):
        for file in conf.return_values('moon file'):
            zerotier['moon_files'].append(file)

    if conf.exists('moon id'):
        for wid in conf.list_nodes('moon id'):
            if conf.exists(f'moon id {wid} root'):
                for root in conf.return_values(f'moon id {wid} root'):
                    zerotier['moon'].append((wid, root))
            else:
                zerotier['moon'].append((wid, None))

    # check if moons have been removed
    if conf.exists_effective('moon id'):
        for wid in conf.list_effective_nodes('moon id'):
            for root in conf.list_effective_nodes(f'moon if {wid} root'):
                if (wid, root) not in zerotier['moon']:
                    zerotier['moon_remove'].append((wid, root))

    return zerotier

def verify(zerotier):
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

    basenames = []
    for file in zerotier['moon_files']:
        basename = os.path.basename(file)
        if basename in basenames:
            raise ConfigError(
                f'There already exists a ZeroTier moon file with the same name '
                f'as "{file}"!')
        basenames.append(basename)

    return True

def generate(zerotier):
    with open(CONFIG_FILE, 'w') as file:
        dump(zerotier['local'], file, indent=4)

    # create moon.d if it doesn't exist
    if not os.path.exists(MOON_DIR):
        os.makedirs(MOON_DIR)
        chown(MOON_DIR, 'zerotier-one', 'zerotier-one')
        chmod_755(MOON_DIR)

    # grab all files in moon directory
    moon_files = [f for f in os.listdir(MOON_DIR) if os.path.isfile(os.path.join(MOON_DIR, f))]

    # grab all files not in config
    remove = [f for f in moon_files if f not in zerotier['moon_files']]
    for file in remove:
        os.remove(f'{MOON_DIR}/{file}')
        zerotier['moons_changed'] = True

    # grab all files not in directory
    add = [f for f in zerotier['moon_files'] if f not in moon_files]
    for file in add:
        _migrate_moon(file)
        zerotier['moons_changed'] = True

    # check if user changed files in the auth directory
    for file in zerotier['moon_files']:
        if not cmp(file, f'{MOON_DIR}/{os.path.basename(file)}'):
            _migrate_moon(file)
            zerotier['moons_changed'] = True


def apply(zerotier):
    if zerotier['moons_changed']:
        # NOTE: this might happen twice, since we also do it in the interfaces file
        cmd('systemctl restart zerotier-one.service')

    cmd('systemctl start zerotier-one.service')

    for wid in zerotier['moon_remove']:
        cmd(f'sudo zerotier-cli deorbit {wid}')

    for wid, root in zerotier['moon']:
        cmd(f'sudo zerotier-cli orbit {wid} {root}')


if __name__ == '__main__':
    try:
        config = get_config()
        verify(config)
        generate(config)
        apply(config)
    except ConfigError as error:
        print(error)
        sys.exit(1)
