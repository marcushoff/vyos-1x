# Copyright 2020 echo reply maintainers and contributors
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

from json import loads

from vyos.util import cmd
from vyos.config import Config

def get_json(path):
    return_json = cmd('sudo zerotier-cli ' + path)
    start_symbols = ['{', '[']
    if return_json[0] not in start_symbols:
        # Bad path, return value is not json
        return None
    return(loads(return_json))

def get_networks():
    return get_json('/network')

def get_network(network):
    return get_json(f'/network/{network}')

def real_interface(network):
    n = get_network(network)
    if n:
        return n['portDeviceName']
    return None

def real_interfaces():
    return [real_interface(n['id']) for n in get_networks()]

def get_moons():
    return get_json(f'/moon')

def get_moon(moon):
    return get_json(f'/moon/{moon}')
    
# returns the configured interface from a real one
def swap_to_configured(intf):

    networks = [n for n in get_networks() if real_interface(n) == intf]
    if len(networks) == 0:
        return None

    conf = Config()
    if not conf.exists_effective('interfaces zerotier'):
        return None

    for z_if in conf.return_effective_values('interfaces zerotier'):
        if conf.exists_effective(f'interfaces zerotier {z_if} network id'):
            net = conf.return_effective_value(f'interfaces zerotier {intf} network id')
            if net == networks[0]:
                return z_if

    return None

# returns the real interface from a configured one
def swap_to_real(intf):
    conf = Config()
    if conf.exists_effective(f'interfaces zerotier {intf} network id'):
        net = conf.return_effective_value(f'interfaces zerotier {intf} network id')
        return real_interface(net)
    return None
