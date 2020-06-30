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

import os

from sys import exit
from copy import deepcopy
from netifaces import interfaces

from vyos.ifconfig import ZeroTierIf
from vyos.config import Config
from vyos.configdict import list_diff
from vyos.validate import is_member
from vyos.util import cmd
from vyos.zerotier import real_interface, get_networks
from vyos import ConfigError


default_config_data = {
    'address': [],
    'address_remove': [],
    'deleted': False,
    'description': '',
    'disable': False,
    'intf': '',
    'is_bridge_member': False,
    'mtu': 1500,
    'vrf': '',
    'network': '',
    'network_remove': '',
    'managed': True,
    'global': False,
    'default': False
}

def get_config():
    zerotier = deepcopy(default_config_data)
    conf = Config()

    # determine tagNode instance
    if 'VYOS_TAGNODE_VALUE' not in os.environ:
        raise ConfigError('Interface (VYOS_TAGNODE_VALUE) not specified')

    zerotier['intf'] = os.environ['VYOS_TAGNODE_VALUE']

    # check if we are a member of any bridge
    zerotier['is_bridge_member'] = is_member(conf, zerotier['intf'], 'bridge')

    # Check if interface has been removed
    if not conf.exists('interfaces zerotier ' + zerotier['intf']):
        zerotier['deleted'] = True
        conf.set_level('interfaces zerotier ' + zerotier['intf'])
        if conf.exists_effective('network'):
            zerotier['network_remove'] = conf.return_effective_value('network id')
        return zerotier

    # set new configuration level
    conf.set_level('interfaces zerotier ' + zerotier['intf'])

    # retrieve configured interface addresses
    if conf.exists('address'):
        zerotier['address'] = conf.return_values('address')

    # retrieve interface description
    if conf.exists('description'):
        zerotier['description'] = conf.return_value('description')

    # Disable this interface
    if conf.exists('disable'):
        zerotier['disable'] = True

    # Determine interface addresses (currently effective) - to determine which
    # address is no longer valid and needs to be removed from the interface
    eff_addr = conf.return_effective_values('address')
    act_addr = conf.return_values('address')
    zerotier['address_remove'] = list_diff(eff_addr, act_addr)

    # Maximum Transmission Unit (MTU)
    if conf.exists(['mtu']):
        zerotier['mtu'] = int(conf.return_value(['mtu']))

    # retrieve VRF instance
    if conf.exists('vrf'):
        zerotier['vrf'] = conf.return_value('vrf')

    acc_network = ''
    eff_network = ''
    if conf.exists_effective('network'):
        eff_network = conf.return_effective_value('network id')

    # retrieve Network ID
    if conf.exists('network'):
        acc_network = conf.return_value('network id')
        if conf.exists('network id'):
            zerotier['network'] = acc_network
        if conf.exists(f'network unmanaged'):
            zerotier['managed'] = False
        if conf.exists(f'network global'):
            zerotier['global'] = True
        if conf.exists(f'network default'):
            zerotier['default'] = True

    # remove old network if different
    if acc_network != eff_network:
        zerotier['network_remove'] = eff_network

    return zerotier

def verify(zerotier):
    if zerotier['deleted']:
        if zerotier['is_bridge_member']:
            raise ConfigError((
                f'Interface "{zerotier["intf"]}" cannot be deleted as it is a '
                f'member of bridge "{zerotier["is_bridge_member"]}"!'))
        return None

    if not zerotier['network']:
        raise ConfigError((
            f'Interface "{zerotier["intf"]}" must belong to a network!'))
    if zerotier['managed'] and len(zerotier['address']):
        raise ConfigError((
            f'Cannot assign address to managed interface "{zerotier["intf"]}"'))

    if zerotier['vrf']:
        if zerotier['vrf'] not in interfaces():
            raise ConfigError(f'VRF "{zerotier["vrf"]}" does not exist')

        if zerotier['is_bridge_member']:
            raise ConfigError((
                f'Interface "{zerotier["intf"]}" cannot be member of VRF '
                f'"{zerotier["vrf"]}" and bridge '
                f'"{zerotier["is_bridge_member"]}" at the same time!'))

    if zerotier['is_bridge_member'] and zerotier['address']:
        raise ConfigError((
            f'Cannot assign address to interface "{zerotier["intf"]}" '
            f'as it is a member of bridge "{zerotier["is_bridge_member"]}"!'))

    return True

def generate(zerotier):
    return None

def apply(zerotier):
    if zerotier['network_remove']:
        cmd(f'sudo zerotier-cli leave {zerotier["network_remove"]}')

    if zerotier['deleted']:
        if len(get_networks()):
            # No more networks running
            cmd('systemctl stop zerotier-one.service')
        return None

# TODO: Error checking on return values from these commands
    cmd('systemctl start zerotier-one.service')
    cmd(f'sudo zerotier-cli join {zerotier["network"]}')
    set_call = f'sudo zerotier-cli set {zerotier["network"]} '
    cmd(set_call + f'allowManaged={int(zerotier["managed"])}')
    cmd(set_call + f'allowGlobal={int(zerotier["global"])}')
    cmd(set_call + f'allowDefault={int(zerotier["default"])}')


    intf = real_interface(zerotier['network'])
    if not intf:
        raise ConfigError((
            f'Unable to find underlying interface for "{zerotier["intf"]}"! '
            f'ZeroTier might not be running or the network hasn\'t been created'
        ))
    z = ZeroTierIf(intf)

# TODO:check if network is in brdige if is bride member

    # update interface description used e.g. within SNMP
    z.set_alias(zerotier['description'])

    # Configure interface address(es)
    # - not longer required addresses get removed first
    # - newly addresses will be added second
    for addr in zerotier['address_remove']:
        z.del_addr(addr)
    for addr in zerotier['address']:
        z.add_addr(addr)

    # assign/remove VRF (ONLY when not a member of a bridge,
    # otherwise 'nomaster' removes it from it)
    if not zerotier['is_bridge_member']:
        z.set_vrf(zerotier['vrf'])

    # Maximum Transmission Unit (MTU)
    z.set_mtu(zerotier['mtu'])

    # disable interface on demand
    if zerotier['disable']:
        z.set_admin_state('down')
    else:
        z.set_admin_state('up')

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
