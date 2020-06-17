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
import json

from vyos import ConfigError
from vyos.config import Config
from vyos.util import call, cmd
#from vyos.template import render

config_file = r'/var/lib/zerotier-one/local.conf'

default_config_data = {
    'network': [],
    'local': {
        'physical': [],
        'virtual': [],
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

    if conf.exists('network'):
        for node in conf.list_nodes('network'):
            network = {
                'id': node,
                'allowManaged': True,
                'allowGlobal': False,
                'allowDefault': False
            }

            if conf.exists('network {0} unmanaged'.format(node)):
                network['allowManaged'] = False
            if conf.exists('network {0} global'.format(node)):
                network['allowGlobal'] = True
            if conf.exists('network {0} default'.format(node)):
                network['allowDefault'] = True

            zerotier['network'].append(network)

    if conf.exists('physical'):
        for node in conf.list_nodes('physical'):
            conf.set_level(base + ' physical {0}'.format(node))
            physical = {
                'blacklist': False,
                'trustedPathId': 0,
                'mtu': 0
            }

            if conf.exists('blacklist'):
                physical['blacklist'] = True
            if conf.exists('trusted-path-id'):
                physical['trustedPathId'] = conf.return_value(['trusted-path-id'])
            if conf.exists('mtu'):
                physical['mtu'] = conf.return_value(['mtu'])

            zerotier['local']['physical'].append({node: physical})
        conf.set_level(base)

    if conf.exists('virtual'):
        for node in conf.list_nodes('virtual'):
            conf.set_level(base + ' virtual {0}'.format(node))
            virtual = {
                'try': [],
                'blacklist': []
            }

            if conf.exists('try address'):
                for t in conf.list_nodes('try address'):
                    if conf.exists('try address {0} port'.format(t)):
                        for p in conf.list_nodes('try address {0} port'.format(t)):
                            virtual['try'].append(address + '/' + p)
                    else:
                        virtual['try'].append(address)
            if conf.exists('blacklist path'):
                for path in conf.list_nodes('blacklist path'):
                    virtual['blacklist'].append(path)

            zerotier['local']['virtual'].append({node: virtual})
        conf.set_level(base)

    if conf.exists('port'):
        conf.set_level(baser + ' port')
        if conf.exists('primary'):
            zerotier['local']['settings']['primaryPort'] = conf.return_value(['primary'])
        if conf.exists('secondary'):
            zerotier['local']['settings']['secondaryPort'] = conf.return_value(['secondary'])
        if conf.exists('tertiary'):
            zerotier['local']['settings']['tertiaryPort'] = conf.return_value(['tertiary'])
        if conf.exists('only-primary'):
            zerotier['local']['settings']['allowSecondaryPort'] = False
        if conf.exists('no-mapping'):
            zerotier['local']['settings']['portMappingEnabled'] = False
        conf.set_level(base)

    if conf.exists('blacklist'):
        for node in conf.list_nodes('interface'):
            zerotier['local']['settings']['interfacePrefixBlacklist'].append(node)

    if conf.exists('no-fallback-relay'):
        zerotier['local']['settings']['allowTcpFallbackRelay'] = False

    if conf.exists('multipath-mode'):
        mapping = {
            'none': 0,
            'random': 1,
            'proportional': 2
        }
        zerotier['local']['settings']['multipathMode'] = mapping[conf.return_value(['multipath-mode'])]

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
    for physical in zerotier['local']['physical']:
        if physical['blacklist'] and (physical['trustedPathId'] or physical['mtu']):
            raise ConfigError('Blacklist is incompatible with other settings')

    # A virtual try address requires a least one port
    for virtual in zerotier['local']['virtual']:
        if not all('/' in t for t in virtual):
            raise ConfigError('At least 1 port is required!')

    return True

def generate(zerotier):
    # bail out early - looks like removal from running config
    if zerotier is None:
        return None

    # bail out early - no networks confiugred
    if len(zerotier['network']) == 0:
        return None

    with open(config_file, 'w') as f:
        json.dump(zerotier['local'], f, indent=4)

    # TODO: Generate moon config files
    return None

def apply(zerotier):
    if zerotier is None:
        call('systemctl stop zerotier-one.service')
        return None

    if len(zerotier['network']) == 0:
        networks = json.loads(cmd('sudo zerotier-cli /network'))
        for network in networks:
            call('sudo zerotier-cli leave {0}'.format(network))

        call('systemctl stop zerotier-one.service')
        return None

    call('systemctl start zerotier-one.service')
    # TODO: Check if we need to resart service if local.conf has changed

    # Go through each network in running zt, see if we should be joined
    networks = json.loads(cmd('sudo zerotier-cli /network'))
    for network in networks:
        # TODO: Check if any method works
        if not any(n for n in zerotier['network'] if n['id'] == network):
            call('sudo zerotier-cli leave {0}'.format(network))

    # Go though all networks in config see if we are joined
    networks = json.loads(cmd('sudo zerotier-cli /network'))
    for network in zerotier['network']:
        if not network['id'] in networks:
            call('sudo zerotier-cli join {0}'.format(network['id']))
        set_call = 'sudo zerotier-cli set {0} '.format(network['id'])
        call(set_call + 'allowManaged {0}'.format(str(network['allowManaged']).lower()))
        call(set_call + 'allowGlobal {0}'.format(str(network['allowGlobal']).lower()))
        call(set_call + 'allowDefault {0}'.format(str(network['allowDefault']).lower()))


if __name__ == '__main__':
    try:
        config = get_config()
        verify(config)
        generate(config)
        apply(config)
    except ConfigError as e:
        print(e)
        exit(1)
