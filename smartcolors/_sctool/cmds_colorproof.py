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

import argparse
import logging

from bitcoin.core import *

from smartcolors.core import *
from smartcolors.core.db import ColorProofDb
from smartcolors._sctool import ParseCOutPointArg

class cmd_prove:
    def __init__(self, subparsers):
        parser = subparsers.add_parser('prove',
                    help='Create a proof that a txout is colored')

        def_or_proof_group = parser.add_mutually_exclusive_group()
        def_or_proof_group.add_argument('-d', metavar='FILE',
                type=argparse.FileType('rb'),
                dest='colordef_fd',
                default=None,
                help='Color definition file')

        def_or_proof_group.add_argument('-p', metavar='FILE',
                type=argparse.FileType('rb'),
                action='append',
                default=[],
                dest='colorproof_fds',
                help='Existing color proof file')

        parser.add_argument('-x', metavar='TXID',
                type=str,
                action='append',
                default=[],
                dest='txids',
                help='Transaction txid to add to the proof')

        parser.add_argument('outpoint', metavar='TXID:N',
                action=ParseCOutPointArg,
                help='Transaction outpoint')

        parser.add_argument('outpoint_proof_fd', metavar='FILE',
                type=argparse.FileType('xb'),
                nargs='?',
                default=None,
                help='Color proof file')

        parser.set_defaults(cmd_func=self.do)

    def do(self, args):
        colordef = None

        db = ColorProofDb()

        for proof_fd in args.colorproof_fds:
            proof = ColorProof.stream_deserialize(proof_fd)

            if colordef is not None:
                if proof.colordef != colordef:
                    args.parser.error('Mismatched colordefs')
            else:
                colordef = proof.colordef

            db.addcolorproof(proof)
            logging.info('Loaded proof: %r' % proof)

        if args.colordef_fd is not None:
            colordef = ColorDef.stream_deserialize(args.colordef_fd)
            db.addcolordef(colordef)

            logging.info('Loaded colordef: %r' % colordef)

        txids = []
        for str_txid in args.txids:
            try:
                txid = lx(str_txid)
            except ValueError as exp:
                args.parser.error('Bad txid: %s' % exp)
            txids.append(txid)

        txids.append(args.outpoint.hash)

        for txid in txids:
            try:
                tx = args.proxy.getrawtransaction(txid)
            except IndexError as exp:
                args.parser.exit("Failed to get tx: %s" % exp)

            db.addtx(tx)
            logging.debug('Added tx to the proof db: %s' % b2lx(tx.GetHash()))

        if args.outpoint not in db.colored_outpoints:
            args.parser.exit("Failed to prove output is colored")

        outpoint_proofs_by_colordef = db.colored_outpoints[args.outpoint]
        assert len(outpoint_proofs_by_colordef.keys()) == 1
        outpoint_proof_set = tuple(outpoint_proofs_by_colordef.values())[0]


        assert len(outpoint_proof_set) == 1 # FIXME: pick best proof
        proof = outpoint_proof_set.pop()

        assert proof.outpoint == args.outpoint

        if args.outpoint_proof_fd is None:
            proof_file_name = '%s:%d.scproof' % (b2lx(args.outpoint.hash), args.outpoint.n)
            args.outpoint_proof_fd = open(proof_file_name, 'xb')
            logging.info('Created proof file %s based on outpoint' % proof_file_name)

        proof.stream_serialize(args.outpoint_proof_fd)
        args.outpoint_proof_fd.close()

class cmd_decodeproof:
    def __init__(self, subparsers):
        parser = subparsers.add_parser('decodeproof',
                    help='Decode a color proof')
        parser.add_argument('fd', metavar='FILE',
                type=argparse.FileType('rb'),
                help='Color proof file')
        parser.set_defaults(cmd_func=self.do)

    def do(self, args):
        proof = ColorProof.stream_deserialize(args.fd)

        print('Proof class: %s' % proof.__class__.__name__)
        print('Colordef: %s' % b2x(proof.colordef.hash))
        print('Outpoint: %s:%d' % (b2lx(proof.outpoint.hash), proof.outpoint.n))

        if isinstance(proof, GenesisOutPointColorProof):
            pass # nothing more to do

        elif isinstance(proof, GenesisScriptPubKeyColorProof):
            print('txid: %s' % b2lx(proof.tx.GetHash()))

        elif isinstance(proof, TransferredColorProof):
            print('txid: %s' % b2lx(proof.tx.GetHash()))
            print('prevout_proofs: %r' % dict(proof.prevout_proofs))

        else:
            assert False
