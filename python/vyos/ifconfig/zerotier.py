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


from vyos.ifconfig.interface import Interface


@Interface.register
class ZeroTierIf(Interface):
    """
    A unique zerotier interface is created for every ZeroTier network joined.
    It disapears once the network is left. The interface will have a randomly
    generated name.
    """

    default = {
        'type': 'zerotier',
    }
    definition = {
        **Interface.definition,
        **{
            'section': 'zerotier',
            'prefixes': ['zt', ],
        },
    }
