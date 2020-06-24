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

from vyos.config import Config
from vyos.validate import is_member
from vyos.util import cmd

def get_network(network):
    n = cmd(f'sudo zerotier-cli /network/{network}')
    if n[0] is not '{' and not '[':
        return None
    return n

def is_running(network):
    n = get_network(network)
    if n:
        return n['id'] == network
    return False

def is_managed(network):
    n = get_network(network)
    if n:
        return n['allowManaged']
    return False

def is_only_interface(network):
    conf = Config()
    old_level = conf.get_level()
    conf.set_level('interfaces')
    count = len(i for i in conf.list_nodes('zerotier') if i['network'] == network)
    if count != 1:
        conf.set_level(old_level)
        return False

    conf.set_level(old_level)
    return True

def real_interface(network):
    n = get_network(network)
    if n:
        return n['portDeviceName']
    return None


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
    'network': ''
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

    # retrieve Network ID
    if conf.exists('network'):
        zerotier['network'] = conf.return_value('network')

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

    if not is_running(zerotier['network']):
        raise ConfigError((
            f'Network "{zerotier["network"]}" on interface "{zerotier["intf"]}" '
            f'doesn\'t exist!'))

    if not is_only_interface(zerotier['network']):
        raise ConfigError((
            f'Only one interface can belong to network "{zerotier["network"]}"!'))

    if is_managed(zerotier['network']) and len(zerotier['address']):
        raise ConfigError((
            f'Cannot assign address to managed interface "{zerotier["intf"]}"'))

    if zerotier['vrf']:
        if zerotier['vrf'] not in interfaces():
            raise ConfigError(f'VRF "{zerotier["vrf"]}" does not exist')

        if zerotier['is_bridge_member']:
            raise ConfigError((
                f'Interface "{zerotier["intf"]}" cannot be member of VRF '
                f'"{zerotier["vrf"]}" and bridge "{zerotier["is_bridge_member"]}"'
                f' at the same time!'))

    if zerotier['is_bridge_member'] and zerotier['address']:
        raise ConfigError((
            f'Cannot assign address to interface "{zerotier["intf"]}" '
            f'as it is a member of bridge "{zerotier["is_bridge_member"]}"!'))

    return True

def generate(zerotier):
    return None

def apply(zerotier):
    intf = real_interface(zerotier['network'])
    if not intf:
        raise ConfigError((
            f'Unable to find underlying interface for "{zerotier["intf"]}"! '
            f'ZeroTier might not be running or the network hasn\'t been created'
        ))
    z = ZerotierIf(intf)

    # Remove dummy interface
    if zerotier['deleted']:
        z.remove()
    else:
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
