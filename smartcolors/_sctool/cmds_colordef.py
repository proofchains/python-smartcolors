#!/usr/bin/env python3

# Copyright (C) 2014 Peter Todd <pete@petertodd.org>
#
# This file is part of python-smartcolors.
#
# It is subject to the license terms in the LICENSE file found in the top-level
# directory of this distribution.
#
# No part of python-smartcolors, including this file, may be copied, modified,
# propagated, or distributed except according to the terms contained in the
# LICENSE file.

"""sctool commands related to color definitions"""

import argparse
import logging
import os

from bitcoin.core import *
from bitcoin.core.script import *
from bitcoin.wallet import CBitcoinAddress

from smartcolors.core import *
from smartcolors._sctool import ParseCOutPointArg

class cmd_definecolor:
    def __init__(self, subparsers):
        parser = subparsers.add_parser('definecolor',
                    help='Create a color definition file')

        parser.add_argument('-x', metavar=('TXID:N', 'QTY'),
            action='append', type=str, nargs=2,
            default=[],
            dest='genesis_outpoints',
            help='Transaction outpoint')
        parser.add_argument('-a', metavar='ADDR',
            action='append', type=str,
            default=[],
            dest='genesis_addrs',
            help='Address')
        parser.add_argument('-s', metavar='SCRIPTPUBKEY',
            action='append', type=str,
            default=[],
            dest='genesis_scriptPubKeys',
            help='Hex-encoded scriptPubKey')
        parser.add_argument('--stegkey', metavar='HEX',
            type=str,
            default=None,
            dest='stegkey',
            help='Stegkey')
        parser.add_argument('--birthdate', metavar='BLOCKHEIGHT',
            type=int,
            default=0,
            dest='birthdate_blockheight',
            help='Birthdate blockheight')
        parser.add_argument('fd', type=argparse.FileType('xb'), metavar='FILE',
            help='Color definition file')
        parser.set_defaults(cmd_func=self.do)

    def do(self, args):
        genesis_outpoints = {}
        genesis_scriptPubKeys = set()

        for str_outpoint, str_qty in args.genesis_outpoints:
            outpoint = ParseCOutPointArg.str_to_COutPoint(str_outpoint, args.parser)
            qty = int(str_qty)

            if outpoint in genesis_outpoints:
                args.parser.exit('dup outpoint %r' % outpoint)

            logging.debug('Genesis outpoint: %s:%d %d' % (b2lx(outpoint.hash), outpoint.n, qty))
            genesis_outpoints[outpoint] = qty

        for str_addr in args.genesis_addrs:
            addr = CBitcoinAddress(str_addr)

            scriptPubKey = addr.to_scriptPubKey()
            if scriptPubKey in genesis_scriptPubKeys:
                args.parser.exit('dup addr %s' % str_addr)

            logging.debug('Genesis scriptPubKey: %s (%s)' % (b2x(scriptPubKey), str(addr)))
            genesis_scriptPubKeys.add(scriptPubKey)

        for hex_scriptPubKey in args.genesis_scriptPubKeys:
            scriptPubKey = CScript(x(hex_scriptPubKey))

            if scriptPubKey in genesis_scriptPubKeys:
                args.parser.exit('dup addr %s' % hex_scriptPubKey)

            logging.debug('Genesis scriptPubKey: %s' % b2x(scriptPubKey))
            genesis_scriptPubKeys.add(scriptPubKey)

        stegkey = os.urandom(ColorDef.STEGKEY_LEN)
        if args.stegkey is not None:
            stegkey = x(args.stegkey)

        colordef = ColorDef(genesis_outpoints=genesis_outpoints,
                            genesis_scriptPubKeys=genesis_scriptPubKeys,
                            birthdate_blockheight=args.birthdate_blockheight,
                            stegkey=stegkey)

        colordef.stream_serialize(args.fd)

class cmd_decodecolordef:
    def __init__(self, subparsers):
        parser = subparsers.add_parser('decodecolordef',
            help='Decode a color definition file')
        parser.add_argument('fd', type=argparse.FileType('rb'), metavar='FILE',
            help='Color definition file')
        parser.set_defaults(cmd_func=self.do)

    def do(self, args):
        colordef = ColorDef.stream_deserialize(args.fd)

        print('ColorDef Hash: %s' % b2x(colordef.hash))
        print('VERSION: %d' % colordef.VERSION)
        print('birthdate blockheight: %d' % colordef.birthdate_blockheight)
        print('stegkey: %s' % b2x(colordef.stegkey))

        print('genesis outpoints:')
        for genesis_outpoint, qty in colordef.genesis_outpoints.items():
            print('    %s:%d %d' % (b2lx(genesis_outpoint.hash), genesis_outpoint.n, qty))

        print('genesis scriptPubKeys:')
        for genesis_scriptPubKey in colordef.genesis_scriptPubKeys.keys():
            print('    %s' % (b2x(genesis_scriptPubKey)))
