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

SCTOOL_VERSION = '0.1.0'

import argparse
import logging

import bitcoin.core
import bitcoin.rpc

class ParseCOutPointArg(argparse.Action):
    @staticmethod
    def str_to_COutPoint(str_outpoint, parser):
        try:
            if str_outpoint.count(':') != 1:
                raise ValueError
            str_txid, str_n = str_outpoint.split(':')

            txid = bitcoin.core.lx(str_txid)
            n = int(str_n)
            return bitcoin.core.COutPoint(txid, n)
        except ValueError as exp:
            parser.exit('Bad outpoint %r: %s' % (str_outpoint, exp))

    def __call__(self, parser, args, values, option_string=None):

        values = self.str_to_COutPoint(values, parser)
        setattr(args, self.dest, values)

def make_arg_parser():
    # Global arguments

    parser = argparse.ArgumentParser(description='Smartcolors tool')

    network_arg_group = parser.add_mutually_exclusive_group()
    network_arg_group.add_argument("-t","--testnet",action='store_true',
                                   help="Use testnet instead of mainnet")
    network_arg_group.add_argument("-r","--regtest",action='store_true',
                                   help="Use regtest instead of mainnet")

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
    parser.add_argument('--version', action='version', version=SCTOOL_VERSION)

    subparsers = parser.add_subparsers()

    import smartcolors._sctool.cmds_colordef
    smartcolors._sctool.cmds_colordef.cmd_definecolor(subparsers)
    smartcolors._sctool.cmds_colordef.cmd_decodecolordef(subparsers)

    return parser


def main(argv, parser=None):
    if parser is None:
        parser = make_arg_parser()

    args = parser.parse_args()
    args.parser = parser

    # Setup logging

    args.verbosity = args.verbose - args.quiet

    if args.verbosity == 1:
        logging.root.setLevel(logging.INFO)
    elif args.verbosity >= 2:
        logging.root.setLevel(logging.DEBUG)
    elif args.verbosity == 0:
        logging.root.setLevel(logging.WARNING)
    elif args.verbosity <= -1:
        logging.root.setLevel(logging.ERROR)


    # Set Bitcoin network globally

    assert not (args.regtest and args.testnet)
    if args.testnet:
        logging.debug('Using testnet')
        bitcoin.SelectParams('testnet')

    elif args.regtest:
        logging.debug('Using regtest')
        bitcoin.SelectParams('regtest')


    args.fee_per_kb = int(args.fee_per_kb * bitcoin.core.COIN)
    logging.debug('Fee-per-kb: %d satoshis/KB' % args.fee_per_kb)

    args.dust = int(args.dust * bitcoin.core.COIN)
    logging.debug('Dust threshold: %d satoshis' % args.dust)

    args.proxy = bitcoin.rpc.Proxy()

    if not hasattr(args, 'cmd_func'):
        parser.error('No command specified')

    args.cmd_func(args)
