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

import re
import unittest
from psutil import process_iter

from vyos.ifconfig import Section
from base_interfaces_test import BasicInterfaceTest
from vyos.configsession import ConfigSessionError
from vyos.util import read_file

def get_config_value(intf, key):
    tmp = read_file(f'/run/wpa_supplicant/{intf}.conf')
    tmp = re.findall(r'\n?{}=(.*)'.format(key), tmp)
    return tmp[0]

class MACsecInterfaceTest(BasicInterfaceTest.BaseTest):
    def setUp(self):
         super().setUp()
         self._base_path = ['interfaces', 'macsec']
         self._options = {
             'macsec0': ['source-interface eth0',
                         'security cipher gcm-aes-128']
         }

         # if we have a physical eth1 interface, add a second macsec instance
         if 'eth1' in Section.interfaces("ethernet"):
             macsec = { 'macsec1': ['source-interface eth1', 'security cipher gcm-aes-128'] }
             self._options.update(macsec)

         self._interfaces = list(self._options)

    def test_encryption(self):
        """ MACsec can be operating in authentication and encryption
        mode - both using different mandatory settings, lets test
        encryption as the basic authentication test has been performed
        using the base class tests """
        intf = 'macsec0'
        src_intf = 'eth0'
        mak_cak = '232e44b7fda6f8e2d88a07bf78a7aff4'
        mak_ckn = '40916f4b23e3d548ad27eedd2d10c6f98c2d21684699647d63d41b500dfe8836'
        replay_window = '64'
        self.session.set(self._base_path + [intf, 'security', 'encrypt'])

        # check validate() - Cipher suite must be set for MACsec
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(self._base_path + [intf, 'security', 'cipher', 'gcm-aes-128'])

        # check validate() - Physical source interface must be set for MACsec
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(self._base_path + [intf, 'source-interface', src_intf])

        # check validate() - MACsec security keys mandartory when encryption is enabled
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(self._base_path + [intf, 'security', 'mka', 'cak', mak_cak])

        # check validate() - MACsec security keys mandartory when encryption is enabled
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(self._base_path + [intf, 'security', 'mka', 'ckn', mak_ckn])

        self.session.set(self._base_path + [intf, 'security', 'replay-window', replay_window])
        self.session.commit()

        tmp = get_config_value(src_intf, 'macsec_integ_only')
        self.assertTrue("0" in tmp)

        tmp = get_config_value(src_intf, 'mka_cak')
        self.assertTrue(mak_cak in tmp)

        tmp = get_config_value(src_intf, 'mka_ckn')
        self.assertTrue(mak_ckn in tmp)

        # check that the default priority of 255 is programmed
        tmp = get_config_value(src_intf, 'mka_priority')
        self.assertTrue("255" in tmp)

        tmp = get_config_value(src_intf, 'macsec_replay_window')
        self.assertTrue(replay_window in tmp)

        # Check for running process
        self.assertTrue("wpa_supplicant" in (p.name() for p in process_iter()))

if __name__ == '__main__':
    unittest.main()
