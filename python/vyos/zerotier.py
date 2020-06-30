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

def get_json(path):
    r = cmd('sudo zerotier-cli ' + path)
    if r[0] is not '{' and not '[':
        # Bad path, return value is not json
        return None
    return(loads(r))

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
    return [real_interface(n) for n in get_networks()]

# returns the configured interface from a real one
def swap_to_configured(intf):
    
    return None

# returns the real interface from a configured one
def swap_to_real(intf):
    return None
