#!/usr/bin/env python3

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

import sys
import argparse
import re

import show_interfaces

from vyos.ifconfig import SectionZT
from vyos.ifconfig import VRRP
from vyos.zerotier import swap_to_real, real_interfaces

def make_real(ifname):
    if re.match(r'^zt[0-9]+$', ifname):
        return swap_to_real(ifname)
    return ifname


def filtered_interfaces(ifnames, iftypes, vif, vrrp):
    """
    get all the interfaces from the OS and returns them
    ifnames can be used to filter which interfaces should be considered

    ifnames: a list of interfaces names to consider, empty do not filter
    return an instance of the interface class
    """
    allnames = SectionZT.interfaces()

    vrrp_interfaces = VRRP.active_interfaces() if vrrp else []

    for ifname in allnames:
        if ifnames and ifname not in ifnames:
            continue

        # return the class which can handle this interface name
        klass = SectionZT.klass(ifname)
        # connect to the interface
        interface = klass(ifname, create=False, debug=False)

        if iftypes and interface.definition['section'] not in iftypes:
            continue

        if vif and not '.' in ifname:
            continue

        if vrrp and ifname not in vrrp_interfaces:
            continue

        yield interface


def get_vrrp_intf():
    return [intf for intf in SectionZT.interfaces() if intf.is_vrrp()]


@show_interfaces.register('help')
def usage(*args):
    print(f"Usage: {sys.argv[0]} [intf=NAME|intf-type=TYPE|vif|vrrp] action=ACTION")
    print("  NAME = " + ' | '.join(SectionZT.interfaces()))
    print("  TYPE = " + ' | '.join(SectionZT.sections()))
    print("  ACTION = " + ' | '.join(actions))
    sys.exit(1)



@show_interfaces.register('allowed')
def run_allowed(**kwarg):
    sys.stdout.write(' '.join(SectionZT.interfaces()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False, description='Show interface information')
    parser.add_argument('--intf', action="store", type=str, default='', help='only show the specified interface(s)')
    parser.add_argument('--intf-type', action="store", type=str, default='', help='only show the specified interface type')
    parser.add_argument('--action', action="store", type=str, default='show', help='action to perform')
    parser.add_argument('--vif', action='store_true', default=False, help="only show vif interfaces")
    parser.add_argument('--vrrp', action='store_true', default=False, help="only show vrrp interfaces")
    parser.add_argument('--help', action='store_true', default=False, help="show help")

    args = parser.parse_args()

    # monkey patch the methods
    show_interfaces.filtered_interfaces = filtered_interfaces
    show_interfaces.get_vrrp_intf = get_vrrp_intf

    def missing(*args):
        print(f'Invalid action [{args.action}]')
        usage()

    show_interfaces.actions.get(args.action, missing)(
        [make_real(_) for _ in args.intf.split(' ') if _],
        [_ for _ in args.intf_type.split(' ') if _],
        args.vif,
        args.vrrp
    )
