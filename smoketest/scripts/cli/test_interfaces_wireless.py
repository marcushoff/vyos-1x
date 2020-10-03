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
import re
import unittest

from base_interfaces_test import BasicInterfaceTest
from vyos.util import process_named_running
from vyos.util import check_kmod
from vyos.util import read_file

def get_config_value(interface, key):
    tmp = read_file(f'/run/hostapd/{interface}.conf')
    tmp = re.findall(r'\n?{}=+(.*)'.format(key), tmp)
    return tmp[0]

class WirelessInterfaceTest(BasicInterfaceTest.BaseTest):
    def setUp(self):
        super().setUp()

        self._base_path = ['interfaces', 'wireless']
        self._options = {
            'wlan0':  ['physical-device phy0', 'ssid VyOS-WIFI-0',
                       'type station', 'address 192.0.2.1/30'],
            'wlan1':  ['physical-device phy0', 'ssid VyOS-WIFI-1',
                       'type access-point', 'address 192.0.2.5/30', 'channel 0'],
            'wlan10': ['physical-device phy1', 'ssid VyOS-WIFI-2',
                       'type station', 'address 192.0.2.9/30'],
            'wlan11': ['physical-device phy1', 'ssid VyOS-WIFI-3',
                       'type access-point', 'address 192.0.2.13/30', 'channel 0'],
        }
        self._interfaces = list(self._options)
        self.session.set(['system', 'wifi-regulatory-domain', 'SE'])

    def test_add_address_single(self):
        """ derived method to check if member interfaces are enslaved properly """
        super().test_add_address_single()

        for option, option_value in self._options.items():
            if 'type access-point' in option_value:
                # Check for running process
                self.assertTrue(process_named_running('hostapd'))
            elif 'type station' in option_value:
                # Check for running process
                self.assertTrue(process_named_running('wpa_supplicant'))
            else:
                self.assertTrue(False)

    def test_hostapd_config(self):
        """ Check if hostapd config is properly generated """

        # Only set the hostapd (access-point) options
        interface = 'wlan0'
        phy = 'phy0'
        ssid = 'ssid'
        channel = '1'

        self.session.set(self._base_path + [interface, 'physical-device', phy])
        self.session.set(self._base_path + [interface, 'ssid', ssid])
        self.session.set(self._base_path + [interface, 'type', 'access-point'])
        self.session.set(self._base_path + [interface, 'channel', channel])
        # auto-powersave is special
        self.session.set(self._base_path + [interface, 'capabilities', 'ht', 'auto-powersave'])

        ht_opt = {
            # VyOS CLI option           hostapd - ht_capab setting
            '40mhz-incapable'         : '[40-INTOLERANT]',
            'delayed-block-ack'       : '[DELAYED-BA]',
            'greenfield'              : '[GF]',
            'ldpc'                    : '[LDPC]',
            'lsig-protection'         : '[LSIG-TXOP-PROT]',
            'channel-set-width ht40+' : '[HT40+]',
            'stbc tx'                 : '[TX-STBC]',
            'stbc rx 123'             : '[RX-STBC-123]',
            'max-amsdu 7935'          : '[MAX-AMSDU-7935]',
            'smps static'             : '[SMPS-STATIC]',
        }
        for key in ht_opt:
            self.session.set(self._base_path + [interface, 'capabilities', 'ht'] + key.split())

        vht_opt = {
            # VyOS CLI option           hostapd - ht_capab setting
            'stbc tx'                 : '[TX-STBC-2BY1]',
            'stbc rx 12'              : '[RX-STBC-12]',
            'ldpc'                    : '[RXLDPC]',
            'tx-powersave'            : '[VHT-TXOP-PS]',
            'vht-cf'                  : '[HTC-VHT]',
            'antenna-pattern-fixed'   : '[RX-ANTENNA-PATTERN][TX-ANTENNA-PATTERN]',
            'max-mpdu 11454'          : '[MAX-MPDU-11454]',
            'max-mpdu-exp 2'          : '[MAX-A-MPDU-LEN-EXP-2][VHT160]',
            'link-adaptation both'    : '[VHT-LINK-ADAPT3]',
            'short-gi 80'             : '[SHORT-GI-80]',
            'short-gi 160'            : '[SHORT-GI-160]',
        }
        for key in vht_opt:
            self.session.set(self._base_path + [interface, 'capabilities', 'vht'] + key.split())

        self.session.commit()

        #
        # Validate Config
        #

        # ssid
        tmp = get_config_value(interface, 'ssid')
        self.assertEqual(ssid, tmp)

        # channel
        tmp = get_config_value(interface, 'channel')
        self.assertEqual(channel, tmp)

        # auto-powersave is special
        tmp = get_config_value(interface, 'uapsd_advertisement_enabled')
        self.assertEqual('1', tmp)

        tmp = get_config_value(interface, 'ht_capab')
        for key, value in ht_opt.items():
            self.assertIn(value, tmp)

        tmp = get_config_value(interface, 'vht_capab')
        for key, value in vht_opt.items():
            self.assertIn(value, tmp)

        # Check for running process
        self.assertTrue(process_named_running('hostapd'))

if __name__ == '__main__':
    check_kmod('mac80211_hwsim')
    unittest.main()
