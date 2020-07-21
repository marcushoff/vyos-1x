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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Completion script used to show zerotier interfaces

from argparse import ArgumentParser

from vyos.zerotier import interfaces, networks, moons


parser = ArgumentParser()
group = parser.add_mutually_exclusive_group()

group.add_argument("-n", "--networks", action='store_true', help="List ZeroTier networks")
group.add_argument("-i", "--interfaces", action='store_true', help="List ZeroTier interfaces")
group.add_argument("-m", "--moons", action='store_true', help="List ZeroTier moons")

args = parser.parse_args()

if args.networks:
    print(" ".join([net['id'] for net in networks()]))
elif args.interfaces:
    print("\n" + " ".join(interfaces()))
elif args.moons:
    print("\n".join([moon['id'] for moon in moons()]))
