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

class SimpleWallet:
    def __init__(self):
        self.secrets_by_scriptPubKey = {}

        # FIXME: hardcoded temp code
        secret = CBitcoinSecret('L3jf5DUv2aticuJJmzpmvMte5oFx7X8YYZUCM5iqE4VkytYnirCK')
        addr = P2PKHBitcoinAddress.from_pubkey(secret.pub) # n4LpQr4EVSZ8YsytrugmyJVyF24Z6fG2DH

        self.secrets_by_scriptPubKey[addr.to_scriptPubKey()] = secret

wallet = SimpleWallet()

# FIXME: all this is temp code
colordef = ColorDef(genesis_outpoint_set=[TxOutGenesisPointDef(COutPoint(lx('a18ed2595af17c30f5968a1c93de2364ae8d5af9d547f2336aafda8ed529fb2e'), 0))])

colorproof = ColorProof(colordef)

def complete_tx(vin, vin_prev_txouts, vout, unspent_txouts, change_scriptPubKey, fee):
    """Complete a transaction

    Adds as many vins from unspent_txouts, change vout with change_scriptPubKey
    """
    vin = list(vin)
    vout = list(vout)

    unspent_txouts = sorted(unspent_txouts, key=lambda txout: txout['amount'])
    sum_out = sum(txout.nValue for txout in vout)
    sum_in = sum(vin_prev_txouts[txin.prevout].nValue for txin in vin)

    logging.debug('sum_in=%d, sum_out=%d' % (sum_in, sum_out))
    while sum_in < sum_out + fee:
        if not unspent_txouts:
            raise Exception('out of unspent outputs')

        new_unspent = unspent_txouts[-1]
        unspent_txouts = unspent_txouts[:-1]

        sum_in += new_unspent['amount']
        new_txin = CTxIn(new_unspent['outpoint'], new_unspent['scriptPubKey'])
        logging.debug('Adding txin %r nValue=%d' % (new_txin.prevout, new_unspent['amount']))
        vin.append(new_txin)

    change_amount = sum_in - (sum_out + fee)
    if change_amount > fee:
        vout.append(CTxOut(change_amount, change_scriptPubKey))

    return (vin, vout)



def pretty_json_dumps(obj):
    return json.dumps(obj, indent=4, sort_keys=True)

def pretty_json_dump(obj, fd):
    fd.write(pretty_json_dumps(obj))
    fd.write('\n')

# Commands

def cmd_issue(args):
    args.addr = CBitcoinAddress(args.addr)
    padded_nValue = add_msbdrop_value_padding(args.qty, minimum_nValue=args.dust)

    issue_txout = bitcoin.core.CTxOut(padded_nValue, args.addr.to_scriptPubKey())

    change_scriptPubKey = args.proxy.getrawchangeaddress().to_scriptPubKey()
    vin, vout = complete_tx([], {}, [issue_txout], args.proxy.listunspent(), change_scriptPubKey, args.fee_per_kb)

    unsigned_genesis_tx = CTransaction(vin, vout)

    r = args.proxy.signrawtransaction(unsigned_genesis_tx)
    if not r['complete']:
        logging.error("Failed to sign tx: %s" % b2x(r['tx'].serialize()))
        sys.exit(1)

    genesis_tx = r['tx']

    logging.debug('Genesis tx: %s' % b2x(genesis_tx.serialize()))

    # Create ColorDef
    #
    # genesis_tx.vout[0] will be our GenesisPoint
    genesis_point = TxOutGenesisPointDef(COutPoint(genesis_tx.GetHash(), 0))
    birthdate_blockheight = args.proxy.getblockcount() - 10
    colordef = ColorDef(genesis_outpoint_set=[genesis_point], birthdate_blockheight=birthdate_blockheight)

    logging.info('New ColorDef hash %s' % b2x(colordef.GetHash()))
    logging.info('New ColorDef: %s' % b2x(colordef.serialize()))

def cmd_sendtoaddress(args):
    cmd_scan(args)

    args.addr = CBitcoinAddress(args.addr)

    # Filter the unspent color outs list against the addresses in our wallet
    sum_color_qty_in = 0
    colored_inputs = []
    for unspent_color_out, qty in colorproof.unspent_outputs.items():
        r = args.proxy.gettxout(unspent_color_out)
        try:
            addr = CBitcoinAddress.from_scriptPubKey(r['txout'].scriptPubKey)
        except CBitcoinAddressError:
            continue

        r = args.proxy.validateaddress(addr)
        if r['ismine']:
            colored_inputs.append(unspent_color_out)
            sum_color_qty_in += qty

            if sum_color_qty_in >= args.qty:
                break

    if sum_color_qty_in < args.qty:
        logging.error("Not enough color available: %d < %d" % (sum_color_qty_in, args.qty))
        sys.exit(1)

    change_qty = sum_color_qty_in - args.qty

    logging.debug('Sum color qty in: %d' % sum_color_qty_in)

    vout = [CTxOut(add_msbdrop_value_padding(args.qty, args.dust), args.addr.to_scriptPubKey())]

    nSequence = 0b1
    if change_qty > 0:
        logging.debug('Adding color change txout: %d' % change_qty)
        nSequence = nSequence << 1 | 0b1

        color_change_addr = args.proxy.getrawchangeaddress()
        color_change_txout = CTxOut(add_msbdrop_value_padding(change_qty, args.dust), color_change_addr.to_scriptPubKey())
        vout.append(color_change_txout)

    vin = [CTxIn(colored_input, nSequence=nSequence) for colored_input in colored_inputs]

    vin_prev_txouts = {txin.prevout:args.proxy.gettxout(txin.prevout)['txout'] for txin in vin}

    # don't spend colored outputs
    unspent_outputs = [unspent for unspent in args.proxy.listunspent()
                           if unspent['outpoint'] not in colorproof.all_outputs]

    vin, vout = complete_tx(vin, vin_prev_txouts,
                            vout,
                            unspent_outputs,
                            args.proxy.getrawchangeaddress().to_scriptPubKey(),
                            args.fee_per_kb)

    unsigned_color_tx = CTransaction(vin, vout)

    r = args.proxy.signrawtransaction(unsigned_color_tx)
    if not r['complete']:
        logging.error("Failed to sign tx: %s" % b2x(r['tx'].serialize()))
        sys.exit(1)

    color_tx = r['tx']

    if args.dry_run:
        logging.info('Tx: %s' % b2x(color_tx.serialize()))

    else:
        txid = args.proxy.sendrawtransaction(color_tx)
        logging.info('Sent txid: %s' % b2lx(txid))



def cmd_scan(args):
    cur_block = 281296

    while cur_block < args.proxy.getblockcount():
        cur_block += 1

        # FIXME: handle reorgs

        block = args.proxy.getblock(args.proxy.getblockhash(cur_block))

        logging.debug('Scanning block %s height %d' % (b2lx(block.GetHash()), cur_block))

        for tx in block.vtx:
            logging.debug('Scanning tx %s' % b2lx(tx.GetHash()))
            colorproof.addtx(tx)

    # Check mempool
    #
    # Ugly because we need to do this in topological order
    logging.debug('Scanning mempool')
    mempool_txs = {txid:args.proxy.getrawtransaction(txid) for txid in args.proxy.getrawmempool()}
    while mempool_txs:
        # Find all mempool_txs that don't depend on other mempool_txs
        root_txs = {}
        for txid, tx in mempool_txs.items():
            is_root = True
            for txin in tx.vin:
                if txin.prevout.hash in mempool_txs:
                    is_root = False
                    break

            if is_root:
                logging.debug('txid %s is a mempool root' % b2lx(txid))
                root_txs[txid] = tx

        for txid in root_txs.keys():
            del mempool_txs[txid]

        logging.debug('adding roots')

        # add those roots
        for tx in root_txs.values():
            colorproof.addtx(tx)

    logging.info('All colored outputs')
    for outpoint, qty in colorproof.all_outputs.items():
        logging.info('    %s %s' % (outpoint, qty))


    logging.info('Unspent colored outputs')
    for outpoint, qty in colorproof.unspent_outputs.items():
        logging.info('    %s %s' % (outpoint, qty))
    logging.info('Unspent sum qty: %d' % sum(colorproof.unspent_outputs.values()))


def cmd_listunspent(args):
    pass


parser = argparse.ArgumentParser(description='Smartcolors demo tool')
parser.add_argument("-t","--testnet",action='store_true',
                             help="Use testnet instead of mainnet")
parser.add_argument("-d","--datadir",type=str,default='~/.smartcolors',
                             help="Data directory")
parser.add_argument("--fee-per-kb",type=float,default=0.0001,
                             help="Fee-per-kb to use")
parser.add_argument("--dust",type=float,default=0.0001,
                             help="Dust threshold")
parser.add_argument("-q","--quiet",action="count",default=0,
                             help="Be more quiet.")
parser.add_argument("-v","--verbose",action="count",default=0,
                             help="Be more verbose. Both -v and -q may be used multiple times.")
parser.add_argument('--version', action='version', version=VERSION)

subparsers = parser.add_subparsers(title='Subcommands',
                                           description='All operations are done through subcommands:')

parser_issue = subparsers.add_parser('issue',
    help='Issue a new color')
parser_issue.add_argument('addr', type=str, metavar='ADDR',
    help='Address')
parser_issue.add_argument('qty', type=int, metavar='QTY',
    help='Quantity of color')
parser_issue.set_defaults(cmd_func=cmd_issue)

parser_sendtoaddress = subparsers.add_parser('sendtoaddress',
    help='Send color to an address')
parser.add_argument('-n', '--dry-run', action='store_true',
        help='Stop before actually doing anything')
parser_sendtoaddress.add_argument('color', type=str, metavar='COLOR',
    help='Color')
parser_sendtoaddress.add_argument('addr', type=str, metavar='ADDR',
    help='Address')
parser_sendtoaddress.add_argument('qty', type=int, metavar='QTY',
    help='Quantity of color')
parser_sendtoaddress.set_defaults(cmd_func=cmd_sendtoaddress)

parser_scan = subparsers.add_parser('scan',
    help='Scan blockchain for new transactions')
parser_scan.set_defaults(cmd_func=cmd_scan)

parser_listunspent = subparsers.add_parser('listunspent',
    help='List unspent colored outputs')
parser_listunspent.set_defaults(cmd_func=cmd_listunspent)

args = parser.parse_args()

args.verbosity = args.verbose - args.quiet

if args.verbosity == 0:
    logging.root.setLevel(logging.INFO)
elif args.verbosity > 1:
    logging.root.setLevel(logging.DEBUG)
elif args.verbosity == -1:
    logging.root.setLevel(logging.WARNING)
elif args.verbosity < -2:
    logging.root.setLevel(logging.ERROR)

if args.testnet:
    logging.debug('Using testnet')
    bitcoin.SelectParams('testnet')

args.fee_per_kb = int(args.fee_per_kb * COIN)
logging.debug('Fee-per-kb: %d satoshis/KB' % args.fee_per_kb)

args.dust = int(args.dust * COIN)
logging.debug('Dust threshold: %d satoshis' % args.dust)

args.proxy = bitcoin.rpc.Proxy()

if not hasattr(args, 'cmd_func'):
    parser.error('No command specified')

args.cmd_func(args)
