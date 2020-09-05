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

import os
import jmespath
import json
import unittest

from vyos.configsession import ConfigSession, ConfigSessionError
from vyos.util import cmd

base_path = ['nat']
source_path = base_path + ['source']

snat_pattern = 'nftables[?rule].rule[?chain].{chain: chain, comment: comment, address: { network: expr[].match.right.prefix.addr | [0], prefix: expr[].match.right.prefix.len | [0]}}'

class TestNAT(unittest.TestCase):
    def setUp(self):
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        self.session = ConfigSession(os.getpid())
        self.session.delete(base_path)

    def tearDown(self):
        self.session.delete(base_path)
        self.session.commit()

    def test_source_nat(self):
        """ Configure and validate source NAT rule(s) """

        network = '192.168.0.0/16'
        self.session.set(source_path + ['rule', '1', 'destination', 'address', network])
        self.session.set(source_path + ['rule', '1', 'exclude'])

        # check validate() - outbound-interface must be defined
        with self.assertRaises(ConfigSessionError):
            self.session.commit()

        self.session.set(source_path + ['rule', '1', 'outbound-interface', 'any'])
        self.session.commit()

        tmp = cmd('sudo nft -j list table nat')
        nftable_json = json.loads(tmp)
        condensed_json = jmespath.search(snat_pattern, nftable_json)[0]

        self.assertEqual(condensed_json['comment'], 'DST-NAT-1')
        self.assertEqual(condensed_json['address']['network'], network.split('/')[0])
        self.assertEqual(str(condensed_json['address']['prefix']), network.split('/')[1])


    def test_validation(self):
        """ T2813: Ensure translation address is specified """
        self.session.set(source_path + ['rule', '100', 'outbound-interface', 'eth0'])

        # check validate() - translation address not specified
        with self.assertRaises(ConfigSessionError):
            self.session.commit()


if __name__ == '__main__':
    unittest.main()
