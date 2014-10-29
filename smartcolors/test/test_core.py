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

import random
import unittest

from bitcoin.core import *
from smartcolors.core import *

class Test_MSB_Drop_padding(unittest.TestCase):
    def test_unpadding(self):
        """MSB-Drop unpadding"""

        def T(padded_nValue, expected_unpadded_nValue):
            actual_unpadded_nValue = remove_msbdrop_value_padding(padded_nValue)
            self.assertEqual(actual_unpadded_nValue, expected_unpadded_nValue)

        # Padding disabled
        T(  0b0,  0b0)
        T( 0b10,  0b1)
        T(0b110, 0b11)
        T(0b1111111111111111111111111111111111111111111111111111111111111110,
          0b111111111111111111111111111111111111111111111111111111111111111)

        # Padding enabled
        T(0b1, 0b0) # degenerate case

        # various ways of representing zero
        T(0b11, 0b0)
        T(0b101, 0b0)
        T(0b1001, 0b0)
        T(0b1000000000000000000000000000000000000000000000000000000000000001,
                                                                        0b0)

        # Smallest representable non-zero number, 1, with various padding sizes
        T(0b111, 0b1)
        T(0b1011, 0b1)
        T(0b10011, 0b1)
        T(0b1000000000000000000000000000000000000000000000000000000000000011,
                                                                        0b1)

        # Largest representable number with largest padding
        T(0b1111111111111111111111111111111111111111111111111111111111111111,
           0b11111111111111111111111111111111111111111111111111111111111111)

        T(0b1100010010101010001011110001101010101101010101010101010101010111,
           0b10001001010101000101111000110101010110101010101010101010101011)

    def test_padding(self):
        """MSB-Drop padding"""

        def T(unpadded_nValue, minimum_nValue, expected_padded_nValue):
            actual_padded_nValue = add_msbdrop_value_padding(unpadded_nValue, minimum_nValue)
            self.assertEqual(actual_padded_nValue, expected_padded_nValue)

            roundtrip_nValue = remove_msbdrop_value_padding(actual_padded_nValue)
            self.assertEqual(roundtrip_nValue, unpadded_nValue)

        # No padding needed w/ zero-minimum
        T(0b0, 0b0,
          0b00)
        T(0b1, 0b0,
          0b10)
        T(0b11, 0b0,
          0b110)
        T(0b111, 0b0,
          0b1110)
        T(0b11111111111111111111111111111111111111111111111111111111111111, 0b0,
          0b111111111111111111111111111111111111111111111111111111111111110)

        # No padding needed as minimum == padded nValue
        T( 0b1, 0b10,
           0b10)
        T( 0b11, 0b110,
           0b110)
        T( 0b101, 0b1010,
           0b1010)

        # Padding needed
        #
        # Various ways to encode zero
        T(0b0, 0b1,
          0b1) # degenerate case, could be encoded as 0b1 w/ special-case

        T(0b0, 0b10,
          0b11)
        T(0b0, 0b11,
          0b11)

        T( 0b0, 0b100,
          0b101)
        T(0b0, 0b101,
          0b101)

        T(  0b0, 0b110,
          0b1001)
        T(  0b0, 0b111,
          0b1001)

        T(  0b0, 0b110,
          0b1001)
        T(  0b0, 0b111,
          0b1001)

        # Encoding non-zero
        T(  0b1, 0b11,
           0b111)
        T(  0b10, 0b101,
           0b1101)
        T(  0b10, 0b1100,
           0b1101)
        T(  0b10, 0b1101,
           0b1101)
        T(   0b10, 0b1110,
           0b10101)
        T(   0b10, 0b1111,
           0b10101)
        T(   0b11, 0b1111,
            0b1111)
        T(  0b100, 0b1111,
           0b11001)

class Test_ColorDef_kernel(unittest.TestCase):
    def make_color_tx(self, kernel, input_nSequences, output_amounts):
        """Make a test transaction"""
        vin = []
        for i, decrypted_nSequence in enumerate(input_nSequences):
            outpoint = COutPoint(n=i)
            nSequence_pad = kernel.nSequence_pad(outpoint)
            txin = CTxIn(outpoint, nSequence=(decrypted_nSequence ^ nSequence_pad))
            vin.append(txin)

        vout = [CTxOut(add_msbdrop_value_padding(nValue, 0)) for nValue in output_amounts]
        return CTransaction(vin, vout)

    def test_no_colored_inputs(self):
        """Degenerate case of no colored inputs or outputs"""
        hdr = ColorDef()
        tx = self.make_color_tx(hdr, [0], [0])
        color_out = hdr.apply_kernel(tx, {})
        self.assertEqual(color_out, [None])

    def test_one_to_one_exact(self):
        """One colored input to one colored output, color_in == max_out"""
        hdr = ColorDef()
        tx = self.make_color_tx(hdr, [0b1], [1])
        color_out = hdr.apply_kernel(tx, {tx.vin[0].prevout:1})
        self.assertEqual(color_out, [1])

    def test_one_to_one_less_than_max(self):
        """One colored input to one colored output, color_in < max_out"""
        hdr = ColorDef()
        tx = self.make_color_tx(hdr, [0b1], [10])
        color_out = hdr.apply_kernel(tx, {tx.vin[0].prevout:1})
        self.assertEqual(color_out, [1])

    def test_one_to_one_more_than_max(self):
        """One colored input to one colored output, color_in > max_out"""
        hdr = ColorDef()
        tx = self.make_color_tx(hdr, [0b1], [1])
        color_out = hdr.apply_kernel(tx, {tx.vin[0].prevout:2})
        self.assertEqual(color_out, [1])

    def test_one_to_two_exact(self):
        """One colored input to two colored outputs, color_in == max_out"""
        hdr = ColorDef()
        tx = self.make_color_tx(hdr, [0b11], [1, 2])
        color_out = hdr.apply_kernel(tx, {tx.vin[0].prevout:3})
        self.assertEqual(color_out, [1, 2])

    def test_one_to_two_less_than_max(self):
        """One colored input to two colored outputs, color_in < max_out"""
        hdr = ColorDef()

        # Exactly enough color in to fill first output but not second
        tx = self.make_color_tx(hdr, [0b11], [1, 2])
        color_out = hdr.apply_kernel(tx, {tx.vin[0].prevout:1})
        self.assertEqual(color_out, [1, None])

        # Enough color in to fill first output and part of second
        tx = self.make_color_tx(hdr, [0b11], [1, 3])
        color_out = hdr.apply_kernel(tx, {tx.vin[0].prevout:3})
        self.assertEqual(color_out, [1, 2])

        # Three colored outputs. The result specifies the last output as
        # colored, but it remains uncolored due to the other two outputs using
        # up all available color.
        tx = self.make_color_tx(hdr, [0b111], [1, 3, 4])
        color_out = hdr.apply_kernel(tx, {tx.vin[0].prevout:3})
        self.assertEqual(color_out, [1, 2, None])

        # As above, but with an uncolored output as well
        tx = self.make_color_tx(hdr, [0b1011], [1, 3, 4, 5])
        color_out = hdr.apply_kernel(tx, {tx.vin[0].prevout:3})
        self.assertEqual(color_out, [1, 2, None, None])

    def test_one_to_two_more_than_max(self):
        """One colored input to two colored outputs, color_in > max_out"""
        hdr = ColorDef()

        # Both filled with one left over
        tx = self.make_color_tx(hdr, [0b11], [1, 2])
        color_out = hdr.apply_kernel(tx, {tx.vin[0].prevout:4})
        self.assertEqual(color_out, [1, 2])

        # Remaining isn't assigned to uncolored outputs
        tx = self.make_color_tx(hdr, [0b11], [1, 2, 3])
        color_out = hdr.apply_kernel(tx, {tx.vin[0].prevout:4})
        self.assertEqual(color_out, [1, 2, None])

    def test_two_to_two_exact(self):
        """Two colored inputs to two colored outputs, color_in == max_out"""
        hdr = ColorDef()

        # 1:1 mapping
        tx = self.make_color_tx(hdr, [0b01, 0b10], [1, 2])
        color_out = hdr.apply_kernel(tx, {tx.vin[0].prevout:1, tx.vin[1].prevout:2})
        self.assertEqual(color_out, [1, 2])

        # Mapping reversed, which means the second input is sending color to
        # both outputs
        tx = self.make_color_tx(hdr, [0b10, 0b11], [1, 2])
        color_out = hdr.apply_kernel(tx, {tx.vin[0].prevout:1, tx.vin[1].prevout:2})
        self.assertEqual(color_out, [1, 2])

    def test_two_to_two_color_left_over(self):
        """Two colored inputs to two colored outputs, color left over but not assigned"""
        hdr = ColorDef()

        tx = self.make_color_tx(hdr, [0b10, 0b01], [2, 3, 4])
        color_out = hdr.apply_kernel(tx, {tx.vin[0].prevout:1, tx.vin[1].prevout:3})
        self.assertEqual(color_out, [2, 1, None])

    def test_multiple_to_one(self):
        hdr = ColorDef()

        tx = self.make_color_tx(hdr, [0b1, 0b1, 0b1, 0b1, 0b1], [1+2+3+4+5])
        color_out = hdr.apply_kernel(tx, {tx.vin[i].prevout:i+1 for i in range(5)})
        self.assertEqual(color_out, [1+2+3+4+5])

        tx = self.make_color_tx(hdr, [0b11, 0b11, 0b11, 0b11, 0b11], [1+2+3+4+5, 100])
        color_out = hdr.apply_kernel(tx, {tx.vin[i].prevout:i+1 for i in range(5)})
        self.assertEqual(color_out, [1+2+3+4+5, None])

    def test_color_assigned_statefully(self):
        """Color is assigned statefully"""
        hdr = ColorDef()
        tx = self.make_color_tx(hdr, [0b11, 0b11], [2, 1])
        color_out = hdr.apply_kernel(tx, {tx.vin[0].prevout:2, tx.vin[1].prevout:1})
        self.assertEqual(color_out, [2, 1])

    def test_zero_color_outputs(self):
        """Zero color qty outputs"""
        hdr = ColorDef()
        tx = self.make_color_tx(hdr, [0b11], [2, 1])
        color_out = hdr.apply_kernel(tx, {tx.vin[0].prevout:2})
        self.assertEqual(color_out, [2, None])

class Test_GenesisOutPointColorProof(unittest.TestCase):
    def test_qty(self):
        outpoint = COutPoint(b'\xaa'*32, n=0)
        cdef = ColorDef(genesis_outpoints={outpoint:42})
        cproof = GenesisOutPointColorProof(cdef, outpoint)

        self.assertEqual(cproof.qty, 42)

    def test_validate(self):
        outpoint = COutPoint(b'\xaa'*32, n=0)
        cdef = ColorDef(genesis_outpoints={outpoint:42})
        cproof = GenesisOutPointColorProof(cdef, COutPoint())

        with self.assertRaises(ColorProofValidationError):
            cproof.validate()

class Test_GenesisScriptPubKeyColorProof(unittest.TestCase):
    def test_qty(self):
        genesis_scriptPubKey = CScript([b'hello world!'])

        tx = CTransaction([], [CTxOut(42 << 1, genesis_scriptPubKey)])
        cdef = ColorDef(genesis_scriptPubKeys=[genesis_scriptPubKey])

        cproof = GenesisScriptPubKeyColorProof(cdef, COutPoint(tx.GetHash(), 0), tx)

        self.assertEqual(cproof.qty, 42)

    def test_validate(self):
        genesis_scriptPubKey = CScript([b'hello world!'])

        tx = CTransaction([], [CTxOut(42 << 1, genesis_scriptPubKey)])
        cdef = ColorDef(genesis_scriptPubKeys=[genesis_scriptPubKey])

        # Outpoint doesn't match transaction
        cproof = GenesisScriptPubKeyColorProof(cdef, COutPoint(), tx)
        with self.assertRaises(ColorProofValidationError):
            cproof.validate()

        # scriptPubKey not a genesis scriptPubKey
        tx = CTransaction([], [CTxOut(42 << 1, CScript([b'wrong']))])
        cproof = GenesisScriptPubKeyColorProof(cdef, COutPoint(tx.GetHash(), 0), tx)
        with self.assertRaises(ColorProofValidationError):
            cproof.validate()

class Test_TransferredColorProof(unittest.TestCase):
    def test_qty(self):
        outpoint = COutPoint(b'\xaa'*32, n=0)
        cdef = ColorDef(genesis_outpoints={outpoint:42})
        genesis_cproof = GenesisOutPointColorProof(cdef, outpoint)

        tx = CTransaction([CTxIn(genesis_cproof.outpoint,
                                 nSequence=(0xFFFFFFFF ^ cdef.nSequence_pad(genesis_cproof.outpoint)))],
                          [CTxOut(42 << 1)])
        tx_cproof = TransferredColorProof(cdef, COutPoint(tx.GetHash(), 0), tx,
                                          {genesis_cproof.outpoint:genesis_cproof})

        self.assertEqual(tx_cproof.qty, 42)

    def test_validate(self):
        outpoint = COutPoint(b'\xaa'*32, n=0)
        cdef = ColorDef(genesis_outpoints={outpoint:42})
        genesis_cproof = GenesisOutPointColorProof(cdef, outpoint)

        tx = CTransaction([CTxIn(genesis_cproof.outpoint,
                                 nSequence=(0xFFFFFFFF ^ cdef.nSequence_pad(genesis_cproof.outpoint)))],
                          [CTxOut(42 << 1)])
        tx_cproof = TransferredColorProof(cdef, COutPoint(tx.GetHash(), 0), tx,
                                          {genesis_cproof.outpoint:genesis_cproof})

        tx_cproof.validate()

        # FIXME: need invalid tests too

