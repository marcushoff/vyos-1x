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
#

from argparse import ArgumentParser

from vyos.util import cmd
from vyos.zerotier import networks


if __name__ == '__main__':
    parser = ArgumentParser()
    group = parser.add_mutually_exclusive_group()

    group.add_argument("-j", "--join", type=str, help="Join ZeroTier network")
    group.add_argument("-l", "--leave", type=str, help="Leave ZeroTier network")

    args = parser.parse_args()

    if args.leave:
        out = cmd(f'sudo zerotier-cli leave {args.leave}')
        if out:
            print(out)

        if len(networks()) <= 0:
            # No more networks running
            cmd('systemctl stop zerotier-one.service')
    elif args.join:
        cmd('systemctl start zerotier-one.service')
        out = cmd(f'sudo zerotier-cli join {args.join}')
        if out:
            print(out)
