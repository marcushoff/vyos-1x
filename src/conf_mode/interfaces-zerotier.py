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

import os
import sys

from copy import deepcopy
from netifaces import interfaces

from vyos.ifconfig import ZeroTierIf
from vyos.config import Config
from vyos.configdict import list_diff
from vyos.validate import is_member
from vyos.util import cmd
import vyos.zerotier as zerotier
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
    'managed': True,
    'global': False,
    'default': False
}

def get_config():
    zt = deepcopy(default_config_data)
    conf = Config()

    # determine tagNode instance
    if 'VYOS_TAGNODE_VALUE' not in os.environ:
        raise ConfigError('Interface (VYOS_TAGNODE_VALUE) not specified')

    zt['intf'] = os.environ['VYOS_TAGNODE_VALUE']

    # check if we are a member of any bridge
    zt['is_bridge_member'] = is_member(conf, zt['intf'], 'bridge')

    # Check if interface has been removed
    if not conf.exists('interfaces zerotier ' + zt['intf']):
        zt['deleted'] = True
        conf.set_level('interfaces zerotier ' + zt['intf'])
        return zt

    # set new configuration level
    conf.set_level('interfaces zerotier ' + zt['intf'])

    # retrieve configured interface addresses
    if conf.exists('address'):
        zt['address'] = conf.return_values('address')

    # retrieve interface description
    if conf.exists('description'):
        zt['description'] = conf.return_value('description')

    # Disable this interface
    if conf.exists('disable'):
        zt['disable'] = True

    # Determine interface addresses (currently effective) - to determine which
    # address is no longer valid and needs to be removed from the interface
    eff_addr = conf.return_effective_values('address')
    act_addr = conf.return_values('address')
    zt['address_remove'] = list_diff(eff_addr, act_addr)

    # Maximum Transmission Unit (MTU)
    if conf.exists(['mtu']):
        zt['mtu'] = int(conf.return_value(['mtu']))

    # retrieve VRF instance
    if conf.exists('vrf'):
        zt['vrf'] = conf.return_value('vrf')

    # retrieve Network ID
    if conf.exists('network'):
        if conf.exists('network unmanaged'):
            zt['managed'] = False
        if conf.exists('network global'):
            zt['global'] = True
        if conf.exists('network default'):
            zt['default'] = True

    return zt

def verify(zt):
    if zt['intf'] not in zerotier.interfaces():
        raise ConfigError((
            f'Interface "{zt["intf"]}" doesn\'t exist! You need to connect to '
            f'the ZeroTier network before configuring the interface.\n'
            f'Use: "connect network zerotier" in op mode'
        ))

    if zt['deleted']:
        if zt['is_bridge_member']:
            raise ConfigError((
                f'Interface "{zt["intf"]}" cannot be deleted as it is a '
                f'member of bridge "{zt["is_bridge_member"]}"!'))
        return None

    if zt['managed'] and len(zt['address']) > 0:
        raise ConfigError((
            f'Cannot assign address to managed interface "{zt["intf"]}"'))

    if zt['vrf']:
        if zt['vrf'] not in interfaces():
            raise ConfigError(f'VRF "{zt["vrf"]}" does not exist')

        if zt['is_bridge_member']:
            raise ConfigError((
                f'Interface "{zt["intf"]}" cannot be member of VRF '
                f'"{zt["vrf"]}" and bridge '
                f'"{zt["is_bridge_member"]}" at the same time!'))

    if zt['is_bridge_member'] and zt['address']:
        raise ConfigError((
            f'Cannot assign address to interface "{zt["intf"]}" '
            f'as it is a member of bridge "{zt["is_bridge_member"]}"!'))

    return True

def generate(zt):
    return None

def apply(zt):
    # assume zerotier is running
    nwid = zerotier.networkid(zt["intf"])
    if not nwid:
        raise ConfigError((
            f'Cannot find ZeroTier network for interface {zt["intf"]}!'
        ))
    # TODO: Error checking on return values from these commands
    set_call = f'sudo zerotier-cli set {nwid} '
    cmd(set_call + f'allowManaged={int(zt["managed"])}')
    cmd(set_call + f'allowGlobal={int(zt["global"])}')
    cmd(set_call + f'allowDefault={int(zt["default"])}')


    z_if = ZeroTierIf(zt['intf'])

    controller_bridge = zerotier.network(nwid)['bridge']
    if zt['is_bridge_member'] and not controller_bridge:
        print(
            f'WARNING: Interface "{zt["intf"]}" is a bridge member, but '
            f'the controller has not set this network to bridge mode!')

    # update interface description used e.g. within SNMP
    z_if.set_alias(zt['description'])

    # Configure interface address(es)
    # - not longer required addresses get removed first
    # - newly addresses will be added second
    for addr in zt['address_remove']:
        z_if.del_addr(addr)
    for addr in zt['address']:
        z_if.add_addr(addr)

    # assign/remove VRF (ONLY when not a member of a bridge,
    # otherwise 'nomaster' removes it from it)
    if not zt['is_bridge_member']:
        z_if.set_vrf(zt['vrf'])

    # Maximum Transmission Unit (MTU)
    z_if.set_mtu(zt['mtu'])

    # disable interface on demand
    if zt['disable']:
        z_if.set_admin_state('down')
    else:
        z_if.set_admin_state('up')


if __name__ == '__main__':
    try:
        config = get_config()
        verify(config)
        generate(config)
        apply(config)
    except ConfigError as error:
        print(error)
        sys.exit(1)
