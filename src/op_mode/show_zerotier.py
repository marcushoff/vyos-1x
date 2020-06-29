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
#

from argparse import ArgumentParser
from tabulate import tabulate
from sys import exit
from json import loads
import time

from vyos.util import cmd, call
from vyos.config import Config


def get_json(path):
    r = cmd('sudo zerotier-cli ' + path)
    if r[0] is not '{' and not '[':
        # Bad path, return value is not json
        return None
    return(loads(r))

def get_localtime(time_in_ms):
    s, ms = divmod(time_in_ms, 1000)
    return '%s.%03d' % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(s)), ms)


if __name__ == '__main__':
    parser = ArgumentParser()

    group = parser.add_mutually_exclusive_group()
    group.add_argument("-i", "--info", action="store_true", help="Show ZeroTier info")
    group.add_argument("-s", "--status", action="store_true", help="Show ZeroTier status")
    group.add_argument("-n", "--network", type=str, nargs='?', const='-1', help="Show ZeroTier network(s)")
    group.add_argument("-r", "--routes", metavar='NETWORK', type=str, help="Show ZeroTier routes for network")
    group.add_argument("-p", "--peer", type=str, nargs='?', const='-1', help="Show ZeroTier peer(s)")
    group.add_argument("-P", "--paths", metavar='PEER', type=str, help="Show ZeroTier paths for peer")
    group.add_argument("-m", "--moon", type=str, nargs='?', const='-1', help="Show ZeroTier moon(s)")
    group.add_argument("-R", "--roots", metavar='MOON', type=str, help="Show ZeroTier roots for moon")

    args = parser.parse_args()

    conf = Config()

    if not conf.exists_effective('vpn zerotier'):
        print('ZeroTier is not configured')
        exit(0)

    if call('systemctl -q is-active zerotier-one.service') != 0:
        print('WARNING: ZeroTier is configured but not started. Data may be invalid')

    if args.info:
        i = cmd('sudo zerotier-cli info').split()
        headers = ['Node address', 'Version', 'Status']
        print(tabulate([i[2:5]], headers))
        exit(0)
    elif args.status:
        j = get_json('/status')

        n = []
        n.append(['Address:', j['address']])
        n.append(['Version:', j['version']])
        n.append(['Status:', 'ONLINE' if j['online'] else 'OFFLINE'])
        n.append(['Clock:', get_localtime(j['clock'])])
        s = j['config']['settings']
        mapping = ('None', 'Random', 'Proportional')
        n.append(['Multipath mode:', mapping[s['multipathMode']]])
        n.append(['Primary port:', s['primaryPort']])

        w = []
        w.append(['Id:', j['planetWorldId']])
        w.append(['Timestamp:', get_localtime(j['planetWorldTimestamp'])])
        w.append(['TCP fallback active:', 'YES' if j['tcpFallbackActive'] else 'NO'])
        node_headers = ['Node', '']
        world_headers = ['World', '']
        print(tabulate(n, node_headers) + '\n')
        print(tabulate(w, world_headers))
        exit(0)
        # TODO: Add zt interfaces to show interfaces list
    elif args.network:
        if args.network is '-1':
            j = get_json('/network')
            headers = ['Network ID', 'Name', 'MAC', 'Status', 'Type', 'Device', 'Assigned IPs']
            networks = []
            for n in j:
                ips = '\n'.join(n['assignedAddresses'])
                networks.append([n['id'], n['name'], n['mac'], n['status'], n['type'], n['portDeviceName'], ips])
            print(tabulate(networks, headers))
        else:
            j = get_json(f'/network/{args.network}')
            if not j:
                print(f'No network {args.network}')
                exit(0)

            n = []
            n.append(['ID:', j['id']])
            n.append(['MAC:', j['mac']])
            n.append(['Name:', j['name']])
            n.append(['Status:', j['status']])
            n.append(['Type:', j['type']])
            n.append(['Allow managed:', j['allowManaged']])
            n.append(['Allow global:', j['allowGlobal']])
            n.append(['Allow default:', j['allowDefault']])
            n.append(['MTU:', j['mtu']])
            n.append(['DHCP:', 'YES' if j['dhcp'] else 'NO'])
            n.append(['Bridge:', j['bridge']])
            n.append(['Broadcast enabled:', j['broadcastEnabled']])
            n.append(['Port error:', j['portError']])
            n.append(['Device:', j['portDeviceName']])
            n.append(['Routes:', len(j['routes'])])

            m = []
            for ms in j['multicastSubscriptions']:
                m.append([ms['adi'], ms['mac']])

            i = [[ip] for ip in j['assignedAddresses']]
            print(tabulate(n, tablefmt='plain') + '\n')
            print(tabulate(i, ['Assigned IPs']) + '\n')
            print('Multicast Subscriptions:\n')
            print(tabulate(m, ['ADI', 'MAC']) + '\n')
        exit(0)
    elif args.routes:
        j = get_json(f'/network/{args.routes}')
        if not j:
            print(f'No network {args.routes}')
            exit(0)

        r = []
        for ro in j['routes']:
            r.append([ro['target'], ro['via'], ro['flags'], ro['metric']])

        print(tabulate(r, ['Target', 'Via', 'Flags', 'Metric']))
        exit(0)
    elif args.peer:
        if args.peer is '-1':
            j = get_json('/peer')

            headers = ['Address', 'Path', 'Latency', 'Version', 'Role']
            peers = []
            for p in j:
                path = '-'
                for pa in p['paths']:
                    if pa['active'] and pa['preferred'] and not pa['expired']:
                        path = pa['address']
                        break
                peers.append([p['address'], path, p['latency'], p['version'], p['role']])

            print(tabulate(peers, headers))
        else:
            j = get_json(f'/peer/{args.peer}')
            if not j:
                print(f'No peer {args.peer}')
                exit(0)

            p = []
            p.append(['Address:', j['address']])
            p.append(['Version:', j['version']])
            p.append(['Latency:', j['latency']])
            p.append(['Role:', j['role']])
            p.append(['Paths:', len(j['paths'])])

            print(tabulate(p, tablefmt='plain'))
        exit(0)
    elif args.paths:
        j = get_json(f'/peer/{args.paths}')
        if not j:
            print(f'No peer {args.paths}')
            exit(0)

        headers = ['Address', 'Last send', 'Last receive', 'Active', 'Expired', 'Preferred', 'Trusted path ID']
        p = []
        for pa in j['paths']:
            send = get_localtime(pa['lastSend'])
            receive = get_localtime(pa['lastReceive'])
            p.append([pa['address'], send, receive, pa['active'], pa['expired'], pa['preferred'], pa['trustedPathId']])

        print(tabulate(p, headers))
        exit(0)
    elif args.moon:
        if args.moon is '-1':
            j = get_json('/moon')

            headers = ['ID', 'Timestamp', 'Waiting', 'Seed']
            moons = []
            for m in j:
                moons.append([m['id'], get_localtime(m['timestamp']), m['waiting'], m['seed']])

            print(tabulate(m, headers))
        else:
            j = get_json(f'/moon/{args.moon}')
            if not j:
                print(f'No moon {args.moon}')
                exit(0)

            m = []
            m.append(['ID:', j['id']])
            m.append(['Timestamp:', get_localtime(j['timestamp'])])
            m.append(['Signature:', j['signature']])
            m.append(['Updates must be signed by:', j['updatesMustBeSignedBy']])
            m.append(['Waiting:', j['waiting']])
            m.append(['Seed:', j['seed']])
            m.append(['Roots:', len(j['roots'])])

            print(tabulate(m, tablefmt='plain'))
        exit(0)
    elif args.roots:
        j = get_json(f'/moon/{args.roots}')
        if not j:
            print(f'No moon {args.roots}')
            exit(0)

        headers = ['Identity', 'Stable endpoints']
        roots = []
        for r in j['roots']:
            roots.append([r['identity'], '\n'.join(r['stableEndpoints'])])

        print(tabulate(roots, headers))
        exit(0)
    else:
        parser.print_help()
        exit(1)
