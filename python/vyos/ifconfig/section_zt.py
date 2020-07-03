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

import re

from vyos.ifconfig import Section


class SectionZT(Section):
    @classmethod
    def _basename(cls, name, vlan):
        """
        remove the trailing characters at the end of interface name
        name: name of the interface
        vlan: if vlan is True, do not stop at the vlan number
        """
        if not re.match(r'^zt[a-z0-9]{8}', name):
            return super(SectionZT, cls)._basename(name, vlan)

        if vlan:
            # vlan not allowed on ZeroTier interfaces, try stripping anyway
            name = name.rstrip('0123456789.')
        return name[0:2]
