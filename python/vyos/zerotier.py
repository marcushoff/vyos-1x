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

def json(path):
    return_json = cmd('sudo zerotier-cli ' + path)
    start_symbols = ['{', '[']
    if return_json[0] not in start_symbols:
        # Bad path, return value is not json
        return None
    return(loads(return_json))

def networks():
    return json('/network')

def network(nwid):
    return json(f'/network/{nwid}')

def interface(nwid):
    n = network(nwid)
    if n:
        return n['portDeviceName']
    return None

def interfaces():
    return [interface(n['id']) for n in networks()]

def moons():
    return json('/moon')

def moon(moon):
    return json(f'/moon/{moon}')

def networkid(intf):
    nwids = [n['id'] for n in networks() if interface(n['id']) == intf]
    if len(nwids) > 0:
        return nwids[0]
    return None

def status():
    return json('/status')

def peers():
    return json('/peer')

def peer(peer):
    return json(f'/peer/{peer}')
