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

VERSION = '0.1.0'

import sys

if sys.version_info.major != 3:
    raise ImportError("Python3 required")

import argparse
import collections
import json
import logging
import time

import bitcoin
import bitcoin.core
import bitcoin.rpc

from bitcoin.core import *
from bitcoin.wallet import *

from smartcolors.core import *

class KnownBlocks:
    def __init__(self, root_dir, proxy):
        os.makedirs(root_dir, exist_ok=True)

        # Files opened in append mode can't be truncated, so open first in
        # append to create, and again to get a normal file handle. FIXME:
        # replace with something less ugly!
        open(root_dir + '/known_blocks', 'ab+')
        self.blocks_fd = open(root_dir + '/known_blocks', 'rb+')

        self.proxy = proxy

    def set_height(self, block_num):
        block_hash = self.proxy.getblockhash(block_num)

        self.blocks_fd.seek(block_num * 32)
        self.blocks_fd.write(block_hash)
        self.blocks_fd.truncate()

    def get_blockhash(self, block_num):
        self.blocks_fd.seek(block_num * 32)
        return self.blocks_fd.read(32)

    def get_height(self):
        self.blocks_fd.seek(0, 2)
        return self.blocks_fd.tell()//32 - 1

    def iter_new_blocks(self):
        while self.get_height() < self.proxy.getblockcount():
            cur_height = self.get_height()
            if cur_height >= 0:
                # Detect reorgs
                cur_hash = self.proxy.getblockhash(cur_height)
                saved_hash = self.get_blockhash(cur_height)
                if cur_hash != saved_hash:
                    logging.info("Reorganizing: height %d, %s -> %s" % (cur_height, b2lx(saved_hash), b2lx(cur_hash)))
                    cur_height -= 1
                    self.blocks_fd.seek(max(0, cur_height * 32))
                    self.blocks_fd.truncate()
                    continue

            cur_height += 1
            new_hash = self.proxy.getblockhash(cur_height)

            self.blocks_fd.seek(cur_height * 32)
            self.blocks_fd.write(new_hash)

            yield (cur_height, new_hash)

class KnownColorDefs:
    def __init__(self, root_dir):
        colordef_dir = root_dir + '/colordef'
        os.makedirs(colordef_dir, exist_ok=True)

        self.defs = []

        self.genesis_outpoint_set = {}

        for colordef_file in os.listdir(colordef_dir):
            logging.info('Loading colordef %s' % colordef_file)

            with open(colordef_dir + '/' + colordef_file, 'rb') as fd:
                colordef = ColorDef.deserialize(fd.read())
                self.defs.append(colordef)

                for genesis_outpoint in colordef.genesis_outpoint_set:
                    d = self.genesis_outpoint_set.setdefault(genesis_outpoint.outpoint, {})
                    assert colordef not in d
                    d[colordef] = genesis_outpoint

                    logging.debug('Genesis txout: %s %d' % (b2lx(genesis_outpoint.outpoint.hash),
                                                            genesis_outpoint.outpoint.n))

class SimpleColorProofDb:
    def __init__(self, root_dir):
        self.root_dir = root_dir
        os.makedirs(self.root_dir + '/tx', exist_ok=True)

        self.known_colordefs = KnownColorDefs(self.root_dir)

    def addtx(self, tx):
        txid = tx.GetHash()
        for i in range(len(tx.vout)):
            outpoint = COutPoint(txid, i)
            try:
                colors = self.known_colordefs.genesis_outpoint_set[outpoint]
            except KeyError:
                continue

            for colordef, genesis_outpoint in colors.items():
                logging.info('%r %r %r' % (outpoint, colordef, genesis_outpoint))

# Commands

def cmd_scan(args):
    if args.height >= 0:
        logging.info("Setting known block height to %d" % args.height)
        args.known_blocks.set_height(args.height)

    for block_height, block_hash in args.known_blocks.iter_new_blocks():
        logging.debug("Block: %d %s" % (block_height, b2lx(block_hash)))

        block = args.proxy.getblock(block_hash)

        for tx in block.vtx:
            logging.debug("Tx: %s" % b2lx(tx.GetHash()))

            args.colordb.addtx(tx)




parser = argparse.ArgumentParser(description='Color database')
parser.add_argument("-t","--testnet",action='store_true',
                             help="Use testnet instead of mainnet")
parser.add_argument("-r","--regtest",action='store_true',
                             help="Use regtest instead of mainnet")
parser.add_argument("-d","--datadir",type=str,default='~/.smartcolors/colordb',
                             help="Data directory")
parser.add_argument("-q","--quiet",action="count",default=0,
                             help="Be more quiet.")
parser.add_argument("-v","--verbose",action="count",default=0,
                             help="Be more verbose. Both -v and -q may be used multiple times.")
parser.add_argument('--version', action='version', version=VERSION)

subparsers = parser.add_subparsers(title='Subcommands',
                                           description='All operations are done through subcommands:')

parser_scan = subparsers.add_parser('scan',
    help='Scan blockchain for new transactions')
parser_scan.add_argument('height', type=int, default=-1, nargs='?',
        help='Starting height')
parser_scan.set_defaults(cmd_func=cmd_scan)

args = parser.parse_args()

args.verbosity = args.verbose - args.quiet

if args.verbosity > 1:
    logging.root.setLevel(logging.DEBUG)

elif args.verbosity == 1:
    logging.root.setLevel(logging.INFO)

elif args.verbosity == 0:
    logging.root.setLevel(logging.WARNING)

elif args.verbosity < 0:
    logging.root.setLevel(logging.ERROR)


if args.testnet and not args.regtest:
    logging.debug('Using testnet')
    bitcoin.SelectParams('testnet')

    args.datadir += '/testnet'

elif args.regtest and not args.testnet:
    logging.debug('Using regtest')
    bitcoin.SelectParams('regtest')

    args.datadir += '/regtest'

elif args.testnet and args.regtest:
    assert(False) # FIXME

else:
    args.datadir += '/mainnet'

args.datadir = os.path.expanduser(args.datadir)

args.proxy = bitcoin.rpc.Proxy()

args.known_blocks = KnownBlocks(args.datadir, args.proxy)
args.colordb = SimpleColorProofDb(args.datadir)

if not hasattr(args, 'cmd_func'):
    parser.error('No command specified')

args.cmd_func(args)
