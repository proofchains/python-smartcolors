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
from smartcolors.io import ColorDefFileSerializer
from smartcolors.db import PersistentColorProofDb

class cmd_db_addcolordef:
    def __init__(self, subparsers):
        parser = subparsers.add_parser('addcolordef',
                    help='Add a color definition to the database')

        parser.add_argument('fd', type=argparse.FileType('rb'), metavar='FILE',
            help='Color definition file')
        parser.set_defaults(cmd_func=self.do)

    def do(self, args):
        colordef = ColorDefFileSerializer.stream_deserialize(args.fd)

        args.colordb.addcolordef(colordef)
        logging.info('Added colordef: %s' % b2x(colordef.hash))

class cmd_db_addtx:
    def __init__(self, subparsers):
        parser = subparsers.add_parser('addtx',
                    help='Add a transaction to the database manually')
        parser.add_argument('txid', type=lx,
            help='Transaction id')
        parser.set_defaults(cmd_func=self.do)

    def do(self, args):
        tx = args.proxy.getrawtransaction(args.txid)
        args.colordb.addtx(tx)

class cmd_db_scan:
    def __init__(self, subparsers):
        parser = subparsers.add_parser('scan',
                    help='Scan the blockchain for colored transactions')
        parser.add_argument('height', type=int,
            help='Starting height')
        parser.set_defaults(cmd_func=self.do)

    def do(self, args):
        cur_height = args.height
        while cur_height <= args.proxy.getblockcount():
            blk_hash = args.proxy.getblockhash(cur_height)
            blk = args.proxy.getblock(blk_hash)
            logging.debug('Blk: %d %s' % (cur_height, b2lx(blk_hash)))

            for tx in blk.vtx:
                args.colordb.addtx(tx)

            cur_height += 1

class cmd_db_statehash:
    def __init__(self, subparsers):
        parser = subparsers.add_parser('statehash',
                    help='Calculate the db state hash')
        parser.set_defaults(cmd_func=self.do)

    def do(self, args):
        state_hash = args.colordb.calc_state_hash()
        print(b2x(state_hash))

def add_db_cmds(subparsers):
    db_parser = subparsers.add_parser('db',
            help='ColorProof Database')

    db_subparsers = db_parser.add_subparsers()

    cmd_db_addcolordef(db_subparsers)
    cmd_db_addtx(db_subparsers)
    cmd_db_scan(db_subparsers)
    cmd_db_statehash(db_subparsers)
