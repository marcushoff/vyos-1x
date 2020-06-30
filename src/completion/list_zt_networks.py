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

# Completion script used to show zerotier networks

# TODO: Change all license to echo reply

from json import loads

from vyos.util import cmd

def get_networks():
    n = cmd(f'sudo zerotier-cli /network')
    if n[0] is not '{' and not '[':
        return None
    return n

print(" ".join([net['id'] for net in loads(get_networks())]))
