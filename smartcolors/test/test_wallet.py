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

import hashlib
import hmac
import random
import unittest

from bitcoin.core import *
from bitcoin.core.script import *

from smartcolors.core import *
from smartcolors.wallet import *

class Test_create_nSequence_color_tx(unittest.TestCase):
    def test_null_case(self):
        vin, vout = create_nSequence_color_tx([], [], lambda change_qty: CSCript())

        self.assertEqual(vin, [])
        self.assertEqual(vout, [])

    def test_no_colored_inputs_outputs(self):
        prevouts = [COutPoint(lx('deadbeef')*8, i) for i in range(8)]
        amounts_out = [(None, CScript([i]), 1) for i in range(8)]
        vin, vout = create_nSequence_color_tx(prevouts, amounts_out, lambda change_qty: CSCript())

        self.assertEqual(vin, [CTxIn(prevout) for prevout in prevouts])
        self.assertEqual(vout, [CTxOut(nValue, scriptPubKey) for qty, scriptPubKey, nValue in amounts_out])

    def test_single_colored_in(self):
        genesis_outpoint = COutPoint(lx('deadbeef')*8, 0)
        colordef = ColorDef(genesis_outpoints={genesis_outpoint:10}, stegkey=b'\x00'*16)
        prevout_proof = GenesisOutPointColorProof(colordef, genesis_outpoint)

        # No change
        vin, vout = create_nSequence_color_tx([prevout_proof], [(10, CScript([b'colored']), None)], None)
        self.assertEqual(vin,
                [CTxIn(COutPoint(lx('deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef'), 0), nSequence=0xc845c1fe)])
        self.assertEqual(vout, [CTxOut(20, CScript([b'colored']))])

        # With change
        vin, vout = create_nSequence_color_tx([prevout_proof], [(1, CScript([b'colored']), None)],
                                              lambda q: CScript([b'change']))
        self.assertEqual(vin,
                [CTxIn(COutPoint(lx('deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef'), 0), nSequence=0xc847c1fe)])
        self.assertEqual(vout,
                [CTxOut( 2, CScript([b'colored'])),
                 CTxOut(18, CScript([b'change']))])

        # One uncolored output
        vin, vout = create_nSequence_color_tx([prevout_proof],
                                              [(1, CScript([b'colored']), None),
                                               (None, CScript([b'notcolored']), 42)],
                                              lambda q: CScript([b'change']),
                                              use_steg=False)
        self.assertEqual(vin,
                [CTxIn(COutPoint(lx('deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef'), 0), nSequence=0x0005007e)])
        self.assertEqual(vout,
                [CTxOut( 2, CScript([b'colored'])),
                 CTxOut(42, CScript([b'notcolored'])),
                 CTxOut(18, CScript([b'change']))])

    def test_multi_colored_in(self):
        genesis_outpoints = [COutPoint(lx('deadbeef')*8, i) for i in range(32)]
        colordef = ColorDef(genesis_outpoints={genesis_outpoint:i for i, genesis_outpoint in enumerate(genesis_outpoints)},
                            stegkey=b'\x00'*16)
        prevout_proofs = [GenesisOutPointColorProof(colordef, genesis_outpoint) for genesis_outpoint in genesis_outpoints]

        # All goes to change
        vin, vout = create_nSequence_color_tx(prevout_proofs, [],
                                              lambda q: CScript([b'change']),
                                              use_steg=False)
        self.assertEqual([CTxIn(COutPoint(lx('deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef'), i), nSequence=0x1007e)
                          for i in range(32)],
                         vin)
        self.assertEqual(vout, [CTxOut(992, CScript([b'change']))])

        # All goes to change w/ one uncolored
        vin, vout = create_nSequence_color_tx(prevout_proofs,
                                              [(None, CScript([b'notcolored']), 42)],
                                              lambda q: CScript([b'change']),
                                              use_steg=False)
        self.assertEqual([CTxIn(COutPoint(lx('deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef'), i), nSequence=0x2007e)
                          for i in range(32)],
                         vin)
        self.assertEqual([CTxOut(42, CScript([b'notcolored'])),
                          CTxOut(992, CScript([b'change']))],
                         vout)

        # One colored, gets everything
        vin, vout = create_nSequence_color_tx(prevout_proofs,
                                              [(496, CScript([b'colored']), None)],
                                              lambda q: None,
                                              use_steg=False)
        self.assertEqual([CTxIn(COutPoint(lx('deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef'), i), nSequence=0x1007e)
                          for i in range(32)],
                         vin)
        self.assertEqual([CTxOut(992, CScript([b'colored']))], vout)

        # Two colored, gets everything
        vin, vout = create_nSequence_color_tx(prevout_proofs,
                                              [(400, CScript([b'colored1']), None),
                                               ( 96, CScript([b'colored2']), None)],
                                              lambda q: None,
                                              use_steg=False)
        self.assertEqual([CTxIn(COutPoint(lx('deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef'), i), nSequence=0x3007e)
                          for i in range(32)],
                         vin)
        self.assertEqual([CTxOut(400<<1, CScript([b'colored1'])),
                          CTxOut(96<<1, CScript([b'colored2']))],
                         vout)
