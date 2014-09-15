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

class Test_GenesisPointDef(unittest.TestCase):
    def test_bad_deserialization(self):
        with self.assertRaises(bitcoin.core.serialize.SerializationError):
            GenesisPointDef.deserialize(b'\x00')
        with self.assertRaises(bitcoin.core.serialize.SerializationError):
            GenesisPointDef.deserialize(b'\x00'*100)

    def test_serialization(self):
        tx_gpt = TxOutGenesisPointDef(COutPoint(b'\x00'*32, 0xffffffff))

        self.assertEqual(tx_gpt.serialize(),
                x('010000000000000000000000000000000000000000000000000000000000000000ffffffff'))

        script_gpt = ScriptPubKeyGenesisPointDef(CScript())
        self.assertEqual(script_gpt.serialize(), x('0200'))

        tx_gpt2 = GenesisPointDef.deserialize(
                        x('010000000000000000000000000000000000000000000000000000000000000000ffffffff'))
        self.assertEqual(tx_gpt2.outpoint, tx_gpt.outpoint)

        script_gpt2 = GenesisPointDef.deserialize(
                        x('0200'))
        self.assertEqual(script_gpt2.scriptPubKey, script_gpt.scriptPubKey)


class Test_ColorDef_kernel(unittest.TestCase):
    def make_color_tx(self, input_nsequences, output_amounts):
        """Make a test transaction"""
        vin = [CTxIn(nSequence=nSequence) for nSequence in input_nsequences]
        vout = [CTxOut(add_msbdrop_value_padding(nValue, 0)) for nValue in output_amounts]
        return CTransaction(vin, vout)

    def test_no_colored_inputs(self):
        """Degenerate case of no colored inputs or outputs"""
        hdr = ColorDef()
        tx = self.make_color_tx([0], [0])
        color_out = hdr.apply_kernel(tx, (None,))
        self.assertEqual(color_out, [None])

    def test_one_to_one_exact(self):
        """One colored input to one colored output, color_in == max_out"""
        hdr = ColorDef()
        tx = self.make_color_tx([0b1], [1])
        color_out = hdr.apply_kernel(tx, (1,))
        self.assertEqual(color_out, [1])

    def test_one_to_one_less_than_max(self):
        """One colored input to one colored output, color_in < max_out"""
        hdr = ColorDef()
        tx = self.make_color_tx([0b1], [10])
        color_out = hdr.apply_kernel(tx, (1,))
        self.assertEqual(color_out, [1])

    def test_one_to_one_more_than_max(self):
        """One colored input to one colored output, color_in > max_out"""
        hdr = ColorDef()
        tx = self.make_color_tx([0b1], [1])
        color_out = hdr.apply_kernel(tx, (2,))
        self.assertEqual(color_out, [1])

    def test_one_to_two_exact(self):
        """One colored input to two colored outputs, color_in == max_out"""
        hdr = ColorDef()
        tx = self.make_color_tx([0b11], [1, 2])
        color_out = hdr.apply_kernel(tx, (3,))
        self.assertEqual(color_out, [1, 2])

    def test_one_to_two_less_than_max(self):
        """One colored input to two colored outputs, color_in < max_out"""
        hdr = ColorDef()

        # Exactly enough color in to fill first output but not second
        tx = self.make_color_tx([0b11], [1, 2])
        color_out = hdr.apply_kernel(tx, (1,))
        self.assertEqual(color_out, [1, 0])

        # Enough color in to fill first output and part of second
        tx = self.make_color_tx([0b11], [1, 3])
        color_out = hdr.apply_kernel(tx, (3,))
        self.assertEqual(color_out, [1, 2])

        # Three colored outputs. The result specifies the last output as
        # colored, but with the amount of color == 0
        tx = self.make_color_tx([0b111], [1, 3, 4])
        color_out = hdr.apply_kernel(tx, (3,))
        self.assertEqual(color_out, [1, 2, 0])

        # As above, but with an uncolored output as well
        tx = self.make_color_tx([0b1011], [1, 3, 4, 5])
        color_out = hdr.apply_kernel(tx, (3,))
        self.assertEqual(color_out, [1, 2, None, 0])

    def test_one_to_two_more_than_max(self):
        """One colored input to two colored outputs, color_in > max_out"""
        hdr = ColorDef()

        # Both filled with one left over
        tx = self.make_color_tx([0b11], [1, 2])
        color_out = hdr.apply_kernel(tx, (4,))
        self.assertEqual(color_out, [1, 2])

        # Remaining isn't assigned to uncolored outputs
        tx = self.make_color_tx([0b11], [1, 2, 3])
        color_out = hdr.apply_kernel(tx, (4,))
        self.assertEqual(color_out, [1, 2, None])

    def test_two_to_two_exact(self):
        """Two colored inputs to two colored outputs, color_in == max_out"""
        hdr = ColorDef()

        # 1:1 mapping
        tx = self.make_color_tx([0b01, 0b10], [1, 2])
        color_out = hdr.apply_kernel(tx, (1,2))
        self.assertEqual(color_out, [1, 2])

        # Mapping reversed, which means the second input is sending color to
        # both outputs
        tx = self.make_color_tx([0b10, 0b11], [1, 2])
        color_out = hdr.apply_kernel(tx, (1,2))
        self.assertEqual(color_out, [1, 2])

    def test_two_to_two_color_left_over(self):
        """Two colored inputs to two colored outputs, color left over but not assigned"""
        hdr = ColorDef()

        tx = self.make_color_tx([0b10, 0b01], [2, 3, 4])
        color_out = hdr.apply_kernel(tx, (1,3))
        self.assertEqual(color_out, [2, 1, None])

    def test_multiple_to_one(self):
        hdr = ColorDef()

        tx = self.make_color_tx([0b1, 0b1, 0b1, 0b1, 0b1], [1+2+3+4+5])
        color_out = hdr.apply_kernel(tx, (1,2,3,4,5))
        self.assertEqual(color_out, [1+2+3+4+5])

        tx = self.make_color_tx([0b11, 0b11, 0b11, 0b11, 0b11], [1+2+3+4+5, 100])
        color_out = hdr.apply_kernel(tx, (1,2,3,4,5))
        self.assertEqual(color_out, [1+2+3+4+5, 0])

class Test_ColorProof(unittest.TestCase):
    def test_simple_addtx(self):
        """addtx() with single input single output chain of txs"""
        genesis_tx = CTransaction(vin=(),
                                  vout=[CTxOut(add_msbdrop_value_padding(1))])

        txout_genesis_point = TxOutGenesisPointDef(COutPoint(genesis_tx.GetHash(), 0))

        cdef = ColorDef([txout_genesis_point])

        cproof = ColorProof(cdef)

        # Proof starts with no outputs proven
        self.assertEqual(len(cproof.all_outputs), 0)
        self.assertEqual(len(cproof.unspent_outputs), 0)

        # the genesis tx adds one output to all, and one to unspent
        genesis_outpoint = COutPoint(genesis_tx.GetHash(), 0)
        expected_all_outputs = {genesis_outpoint: 1}
        expected_unspent_outputs = {genesis_outpoint: 1}

        cproof.addtx(genesis_tx)

        self.assertEqual(cproof.all_outputs, expected_all_outputs)
        self.assertEqual(cproof.unspent_outputs, expected_unspent_outputs)

        # spend the genesis output, creating a new output
        tx2 = CTransaction(vin=[CTxIn(prevout=genesis_outpoint)],
                           vout=[CTxOut(add_msbdrop_value_padding(1))])

        tx2_colored_outpoint = COutPoint(tx2.GetHash(), 0)
        expected_all_outputs[tx2_colored_outpoint] = 1
        del expected_unspent_outputs[genesis_outpoint]
        expected_unspent_outputs[tx2_colored_outpoint] = 1

        cproof.addtx(tx2)

        self.assertEqual(cproof.all_outputs, expected_all_outputs)
        self.assertEqual(cproof.unspent_outputs, expected_unspent_outputs)

        # again
        tx3 = CTransaction(vin=[CTxIn(prevout=tx2_colored_outpoint)],
                           vout=[CTxOut(add_msbdrop_value_padding(1))])

        tx3_colored_outpoint = COutPoint(tx3.GetHash(), 0)
        expected_all_outputs[tx3_colored_outpoint] = 1
        del expected_unspent_outputs[tx2_colored_outpoint]
        expected_unspent_outputs[tx3_colored_outpoint] = 1

        cproof.addtx(tx3)

        self.assertEqual(cproof.all_outputs, expected_all_outputs)
        self.assertEqual(cproof.unspent_outputs, expected_unspent_outputs)

        # destroy the color, resulting in no unspent colored outputs
        tx4 = CTransaction(vin=[CTxIn(prevout=tx3_colored_outpoint, nSequence=0)],
                           vout=[CTxOut(add_msbdrop_value_padding(1))]) # won't be colored

        del expected_unspent_outputs[tx3_colored_outpoint]

        cproof.addtx(tx4)

        self.assertEqual(cproof.all_outputs, expected_all_outputs)
        self.assertEqual(cproof.unspent_outputs, expected_unspent_outputs)

        # test the test!
        self.assertEqual(expected_unspent_outputs, {})
        self.assertEqual(len(expected_all_outputs), 3)

    def test_complex_addtx(self):
        """addtx() with complex, randomized, multi-input multi-output set of transactions"""

        # create a set of n genesis transactions each with (1, m) genesis outputs
        n = 100
        m = 10
        genesis_txs = []
        genesis_points = []
        sum_genesis_color_qty = 0
        expected_all_outputs = {}
        expected_unspent_outputs = {}
        for i in range(n):
            vin = ()

            vout = []
            for i in range(random.randint(1, m)):
                # randomly chosen amount of color
                color_qty = random.randint(1, 2**32)
                sum_genesis_color_qty += color_qty

                txout = CTxOut(add_msbdrop_value_padding(color_qty))
                vout.append(txout)

            genesis_tx = CTransaction(vin, vout)
            genesis_txs.append(genesis_tx)

            # create genesis points from those outputs
            for i, txout in enumerate(genesis_tx.vout):
                outpoint = COutPoint(genesis_tx.GetHash(), i)
                color_qty = remove_msbdrop_value_padding(txout.nValue)

                expected_all_outputs[outpoint] = color_qty
                expected_unspent_outputs[outpoint] = color_qty

                txout_genesis_point = TxOutGenesisPointDef(outpoint)
                genesis_points.append(txout_genesis_point)

        cdef = ColorDef(genesis_points)

        cproof = ColorProof(cdef)
        for genesis_tx in genesis_txs:
            cproof.addtx(genesis_tx)

        # unspent and all outputs should be identical
        self.assertEqual(cproof.all_outputs, cproof.unspent_outputs)

        # check how much color there is
        self.assertEqual(sum(cproof.unspent_outputs.values()), sum_genesis_color_qty)

        # Create n transactions spending the colored outputs, conserving color.
        n = 1
        for i in range(n):
            # spend a random subset of all unspent outputs
            unspent_subset = random.sample(cproof.unspent_outputs.items(),
                                           random.randint(1, 32))

            sum_in = sum(color_qty for outpoint, color_qty in unspent_subset)
            self.assertTrue(sum_in > 0)

            vin = [CTxIn(outpoint) for outpoint, color_qty in unspent_subset]

            # Create outputs.
            #
            # Random # of outputs created such that inputs ~= outputs, subject
            # to precision limitations on color qty.
            vout = []
            num_outs = random.randint(0, 31)
            remaining_color = sum_in
            sum_out = 0
            for j in range(num_outs):
                self.assertTrue(remaining_color >= 0)
                if remaining_color == 0:
                    break
                color_qty = min(remaining_color, random.randint(1, sum_in // num_outs))
                if j == num_outs-1:
                    color_qty = remaining_color
                remaining_color -= color_qty
                sum_out += color_qty
                txout = CTxOut(add_msbdrop_value_padding(color_qty))
                vout.append(txout)

            tx = CTransaction(vin, vout)

            import pdb; pdb.set_trace()
            cproof.addtx(tx)

            sum_out2 = sum(cproof.unspent_outputs[COutPoint(tx.GetHash(), i)] for i in range(len(tx.vout)))

            for vin in tx.vin:
                del expected_unspent_outputs[vin.prevout]
                self.assertNotIn(vin.prevout, cproof.unspent_outputs)

            for i, txout in enumerate(tx.vout):
                outpoint = COutPoint(tx.GetHash(), i)
                color_qty = remove_msbdrop_value_padding(txout.nValue)

                import pdb; pdb.set_trace()

                expected_all_outputs[outpoint] = color_qty
                self.assertEqual(cproof.all_outputs[outpoint], color_qty)

                expected_unspent_outputs[outpoint] = color_qty
                self.assertEqual(cproof.unspent_outputs[outpoint], color_qty)


        self.assertEqual(cproof.all_outputs, expected_all_outputs)
        self.assertEqual(cproof.all_unspent_outputs, expected_unspent_outputs)
