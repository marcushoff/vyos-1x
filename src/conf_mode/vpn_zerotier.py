#!/usr/bin/env python3
#
# Copyright (C) 2018-2020 VyOS maintainers and contributors
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
from json import dump, loads

from vyos import ConfigError
from vyos.config import Config
from vyos.util import call, cmd

config_file = r'/var/lib/zerotier-one/local.conf'

default_config_data = {
    'network': [],
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
    local = zerotier['local']

    if conf.exists('network'):
        for node in conf.list_nodes('network'):
            network = {
                'id': node,
                'allowManaged': True,
                'allowGlobal': False,
                'allowDefault': False
            }

            if conf.exists(f'network {node} unmanaged'):
                network['allowManaged'] = False
            if conf.exists(f'network {node} global'):
                network['allowGlobal'] = True
            if conf.exists(f'network {node} default'):
                network['allowDefault'] = True

            zerotier['network'].append(network)

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
                    if not len(ports):
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

    return zerotier

def verify(zerotier):
    # bail out early - looks like removal from running config
    if zerotier is None:
        return None

    # bail out early - no networks confiugred
    if len(zerotier['network']) == 0:
        print('Warning: No ZeroTier networks defined, the service will be deactivated')
        return None

    # Physical blacklist cannot coexist with other settings
    p = zerotier['local']['physical']
    for key in p:
        if p[key]['blacklist'] and (p[key]['trustedPathId'] or p[key]['mtu']):
            raise ConfigError('ZeroTier blacklist is incompatible with other settings')

    # A virtual try address requires a least one port
    virtual = zerotier['local']['virtual']
    for key in virtual:
        if not all('/' in t for t in virtual[key]['try']):
            raise ConfigError('ZeroTier virtual try requires at least 1 port')

    return True

def generate(zerotier):
    # bail out early - looks like removal from running config
    if zerotier is None:
        return None

    # bail out early - no networks confiugred
    if len(zerotier['network']) == 0:
        return None

    with open(config_file, 'w') as f:
        dump(zerotier['local'], f, indent=4)

    # TODO: Generate moon config files
    return None

def apply(zerotier):
    if zerotier is None:
        cmd('systemctl stop zerotier-one.service')
        return None

    if len(zerotier['network']) == 0:
        networks = loads(cmd('sudo zerotier-cli /network'))
        for network in networks:
            cmd(f'sudo zerotier-cli leave {network["id"]}')

        cmd('systemctl stop zerotier-one.service')
        return None

    cmd('systemctl start zerotier-one.service')

    # Go through each network in running zt, see if we should be joined
    networks = loads(cmd('sudo zerotier-cli /network'))
    for network in networks:
        if not any(n for n in zerotier['network'] if n['id'] == network['id']):
            cmd(f'sudo zerotier-cli leave {network["id"]}')

    # Go though all networks in config see if we are joined
    networks = loads(cmd('sudo zerotier-cli /network'))
    for network in zerotier['network']:
        if not any(n for n in networks if n['id'] == network['id']):
            cmd(f'sudo zerotier-cli join {network["id"]}')
        set_call = f'sudo zerotier-cli set {network["id"]} '
        cmd(set_call + f'allowManaged={int(network["allowManaged"])}')
        cmd(set_call + f'allowGlobal={int(network["allowGlobal"])}')
        cmd(set_call + f'allowDefault={int(network["allowDefault"])}')


if __name__ == '__main__':
    try:
        config = get_config()
        verify(config)
        generate(config)
        apply(config)
    except ConfigError as e:
        print(e)
        exit(1)
