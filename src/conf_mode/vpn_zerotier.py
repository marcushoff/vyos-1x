#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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

from copy import deepcopy
from sys import exit
from json import dump

from vyos import ConfigError
from vyos.config import Config
from vyos.util import call, cmd

config_file = r'/var/lib/zerotier-one/local.conf'

default_config_data = {
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
}

def get_config():
    zerotier = deepcopy(default_config_data)
    conf = Config()
    base = 'vpn zerotier'
    if not conf.exists(base):
        return None
    else:
        conf.set_level(base)
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

            zerotier['physical'][node] = physical
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
                    if not len(ports):
                        virtual['try'].append(address)
            if conf.exists('blacklist path'):
                virtual['blacklist'] = conf.return_values(['blacklist path'])

            zerotier['virtual'][node] = virtual
        conf.set_level(base)

    if conf.exists('port'):
        conf.set_level(base + ' port')
        if conf.exists('primary'):
            zerotier['settings']['primaryPort'] = int(conf.return_value(['primary']))
        if conf.exists('secondary'):
            zerotier['settings']['secondaryPort'] = int(conf.return_value(['secondary']))
        if conf.exists('tertiary'):
            zerotier['settings']['tertiaryPort'] = int(conf.return_value(['tertiary']))
        if conf.exists('only-primary'):
            zerotier['settings']['allowSecondaryPort'] = False
        if conf.exists('no-mapping'):
            zerotier['settings']['portMappingEnabled'] = False
        conf.set_level(base)

    if conf.exists('blacklist'):
        zerotier['settings']['interfacePrefixBlacklist'] = conf.return_values(['blacklist interface'])

    if conf.exists('no-fallback-relay'):
        zerotier['settings']['allowTcpFallbackRelay'] = False

    if conf.exists('multipath-mode'):
        mapping = {
            'none': 0,
            'random': 1,
            'proportional': 2
        }
        zerotier['settings']['multipathMode'] = mapping[conf.return_value(['multipath-mode'])]

    return zerotier

def verify(zerotier):
    # bail out early - looks like removal from running config
    if zerotier is None:
        return None

    # Physical blacklist cannot coexist with other settings
    p = zerotier['physical']
    for key in p:
        if p[key]['blacklist'] and (p[key]['trustedPathId'] or p[key]['mtu']):
            raise ConfigError('ZeroTier blacklist is incompatible with other settings')

    # A virtual try address requires a least one port
    virtual = zerotier['virtual']
    for key in virtual:
        if not all('/' in t for t in virtual[key]['try']):
            raise ConfigError('ZeroTier virtual try requires at least 1 port')

    return True

def generate(zerotier):
    # bail out early - looks like removal from running config
    if zerotier is None:
        return None

    with open(config_file, 'w') as f:
        dump(zerotier, f, indent=4)

    # TODO: Generate moon config files
    return None

def apply(zerotier):
    return None

if __name__ == '__main__':
    try:
        config = get_config()
        verify(config)
        generate(config)
        apply(config)
    except ConfigError as e:
        print(e)
        exit(1)
