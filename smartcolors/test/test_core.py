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

class Test_CTransactionSerializer(unittest.TestCase):
    def test_hash(self):
        """Manual test of the hash calculation"""
        def h(buf):
            return hmac.HMAC(x('4668df91fe332d65378cc758958d701d'), buf, hashlib.sha256).digest()

        serialized_tx = x('01000000010000000000000000000000000000000000000000000000000000000000000000ffffffff0704ffff001d0104ffffffff0100f2052a0100000043410496b538e853519c726a2c91e61ec11600ae1390813a627c66fb8be7947be63c52da7589379515d4e0a604f8141781e62294721166bf621e73a82cbf2342c858eeac00000000')
        tx = CTransaction.deserialize(serialized_tx)

        # hash is LE128 length + serialized_tx
        expected_hash = h(b'\x86\x01' + serialized_tx)
        self.assertEqual(b2x(expected_hash), b2x(CTransactionSerializer.calc_hash(tx)))

class Test_COutPointSerializer(unittest.TestCase):
    def test_hash(self):
        """Manual test of the hash calculation"""
        def h(buf):
            return hmac.HMAC(x('eac9aef052700336a94accea6a883e59'), buf, hashlib.sha256).digest()

        serialized_outpoint = x('3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a00000000')
        outpoint = COutPoint.deserialize(serialized_outpoint)

        # hash is LE128 length + serialized_tx
        expected_hash = h(serialized_outpoint)
        self.assertEqual(b2x(expected_hash), b2x(COutPointSerializer.calc_hash(outpoint)))

class Test_CScriptSerializer(unittest.TestCase):
    def test_hash(self):
        """Manual test of the hash calculation"""
        def h(buf):
            return hmac.HMAC(x('3b808252881682adf56f7cc5abc0cb3c'), buf, hashlib.sha256).digest()

        # hash is LE128 length + script
        expected_hash = h(x('0d') + # LE128 script length
                          b'\x0chello world!')

        script = CScript(b'\x0chello world!')
        self.assertEqual(b2x(expected_hash), b2x(CScriptSerializer.calc_hash(script)))

class Test_ColorDef_kernel(unittest.TestCase):
    def make_color_tx(self, kernel, input_nSequences, output_amounts):
        """Make a test transaction"""
        vin = []
        for i, nSequence in enumerate(input_nSequences):
            outpoint = COutPoint(n=i)
            nSequence <<= 16
            nSequence |= 0x7E
            txin = CTxIn(outpoint, nSequence=nSequence)
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
    def test_hash(self):
        """Manual test of the hash calculation"""
        def h(buf):
            return hmac.HMAC(x('b96dae8e52cb124d01804353736a8384'), buf, hashlib.sha256).digest()

        genesis_outpoint = COutPoint(lx('4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b'), 0)

        colordef = ColorDef.deserialize(x('0100ec746756751d8ac6e9345f9050e1565f013ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a0000000080e497d01200'))

        colorproof = GenesisOutPointColorProof(colordef, genesis_outpoint)

        expected_hash = h(x('01') + # ColorProof type
                          x('01') + # version
                          colordef.hash +
                          COutPointSerializer.calc_hash(genesis_outpoint))

        self.assertEqual(b2x(expected_hash), b2x(colorproof.hash))

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
    def test_hash(self):
        """Manual test of the hash calculation"""
        def h(buf):
            return hmac.HMAC(x('b96dae8e52cb124d01804353736a8384'), buf, hashlib.sha256).digest()

        genesis_scriptPubKey = CScript([b'hello world!'])
        colordef = ColorDef.deserialize(x('01006bbd59a72d6a9b5629b0162a4ab90f3b00010d0c68656c6c6f20776f726c6421'))

        tx = CTransaction.deserialize(x('01000000010000000000000000000000000000000000000000000000000000000000000000ffffffff4d04ffff001d0104455468652054696d65732030332f4a616e2f32303039204368616e63656c6c6f72206f6e206272696e6b206f66207365636f6e64206261696c6f757420666f722062616e6b73ffffffff0100f2052a01000000434104678afdb0fe5548271967f1a67130b7105cd6a828e03909a67962e0ea1f61deb649f6bc3f4cef38c4f35504e51ec112de5c384df7ba0b8d578a4c702b6bf11d5fac00000000'))

        outpoint = COutPoint(tx.GetHash(), 0)
        colorproof = GenesisScriptPubKeyColorProof(colordef, outpoint, tx)

        expected_hash = h(x('02') + # ColorProof type
                          x('01') + # version
                          colordef.hash +
                          x('00') + # n
                          CTransactionSerializer.calc_hash(tx))

        self.assertEqual(b2x(expected_hash), b2x(colorproof.hash))

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
    def test_hash(self):
        """Manual test of the hash calculation"""

        genesis_outpoint = COutPoint(lx('4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b'), 0)
        genesis_scriptPubKey = CScript([b'hello world!'])

        # colordef has the above genesis outpoint, and the above genesis
        # scriptPubKey
        colordef = ColorDef.deserialize(x('0100e21a56b106c2b720ed82c603471b5d55013ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a0000000080e497d012010d0c68656c6c6f20776f726c6421'))

        tx_genesis_scriptPubKey = \
                CTransaction([CTxIn(COutPoint(lx('0e3e2357e806b6cdb1f70b54c3a3a17b6714ee1f0e68bebb44a74b1efd512098'), 0))],
                             [CTxOut(1 << 1, genesis_scriptPubKey)],
                             nLockTime=5) # used to make first bit in merbinner tree collide, and second not collide

        # So we can create valid color proofs for both
        outpoint_colorproof = GenesisOutPointColorProof(colordef, genesis_outpoint)
        scriptPubKey_colorproof = GenesisScriptPubKeyColorProof(colordef, COutPoint(tx_genesis_scriptPubKey.GetHash(),0), tx_genesis_scriptPubKey)

        # And spend both in a valid transaction (er, well, we don't have satoshi's private key...)
        tx = CTransaction([CTxIn(genesis_outpoint, nSequence=0xFFFF007E),
                           CTxIn(COutPoint(tx_genesis_scriptPubKey.GetHash(),0), nSequence=0xFFFF007E)],
                          [CTxOut(1 << 1)]) # we kinda destroyed a lot of color there...

        outpoint = COutPoint(tx.GetHash(), 0)
        colorproof = TransferredColorProof(colordef, outpoint, tx,
                                           prevout_proofs={tx.vin[0].prevout:outpoint_colorproof,
                                                           tx.vin[1].prevout:scriptPubKey_colorproof})

        # The prevout proofs merbinner tree is a relatively complex structure,
        # so test it explicitly first. Of course, merbinner trees are tested
        # elsewhere, but this is sufficiently critical that we still should
        # test it explicitly here.
        def h(buf):
            return hmac.HMAC(x('486a3b9f0cc1adc7f0f7f3e388b89dbc'), buf, hashlib.sha256).digest()

        self.assertEqual('f2eea3c6203bebe501c42ac420469afca0cee4e48a67d8754c449b832b1d084c',
                b2x(COutPointSerializer.calc_hash(tx.vin[0].prevout)))
        self.assertEqual('aae7c112d92b9dcab3ae78b78884c77e092b94a56941cf05c5f406ef40daf2f2',
                b2x(COutPointSerializer.calc_hash(tx.vin[1].prevout)))

        # Structure of the merbinner tree is Inner(Inner(Leaf[outpoint], Leaf[script]), Empty]),
        # which we've brute-forced above explicitly to exercise all the
        # relevant cases.
        expected_hash = h(x('02') +
                          h(x('02') + # Inner node on left side
                            h(x('01') + # Leaf node, genesis outpoint proof
                              COutPointSerializer.calc_hash(tx.vin[0].prevout) +
                              outpoint_colorproof.hash
                             ) +
                            x('80e497d012') + # sum for the genesis outpoint leaf, 5,000,000,000 qty of color (!)
                            h(x('01') + # Leaf node, scriptPubKey proof
                              COutPointSerializer.calc_hash(tx.vin[1].prevout) +
                              scriptPubKey_colorproof.hash
                             ) +
                            x('01') # sum for the scriptPubKey proof leaf; 1 qty of color
                           ) +
                          x('81e497d012') + # sum for the inner node, 5,000,000,001 qty of color
                          h(x('00')) + # empty node on right side
                          x('00') # empty nodes have 0 color of course
                         )

        colorproof.prevout_proofs.calc_hash()
        self.assertEqual(b2x(expected_hash), b2x(colorproof.prevout_proofs.hash))

        # redefine for the TransferredColorProof hash calculation
        def h(buf):
            return hmac.HMAC(x('b96dae8e52cb124d01804353736a8384'), buf, hashlib.sha256).digest()

        expected_hash = h(x('03') + # ColorProof type
                          x('01') + # version
                          colordef.hash +
                          x('00') + # n
                          CTransactionSerializer.calc_hash(tx) +
                          colorproof.prevout_proofs.hash)

        self.assertEqual(b2x(expected_hash), b2x(colorproof.hash))

    def test_qty(self):
        outpoint = COutPoint(b'\xaa'*32, n=0)
        cdef = ColorDef(genesis_outpoints={outpoint:42})
        genesis_cproof = GenesisOutPointColorProof(cdef, outpoint)

        tx = CTransaction([CTxIn(genesis_cproof.outpoint,
                                 nSequence=(0xFE | (0xFFFFFF00 & (0xFFFF0000 ^ cdef.nSequence_pad(genesis_cproof.outpoint)))))],
                          [CTxOut(42 << 1)])
        tx_cproof = TransferredColorProof(cdef, COutPoint(tx.GetHash(), 0), tx,
                                          {genesis_cproof.outpoint:genesis_cproof})

        self.assertEqual(tx_cproof.qty, 42)

    def test_validate(self):
        outpoint = COutPoint(b'\xaa'*32, n=0)
        cdef = ColorDef(genesis_outpoints={outpoint:42})
        genesis_cproof = GenesisOutPointColorProof(cdef, outpoint)

        tx = CTransaction([CTxIn(genesis_cproof.outpoint,
                                 nSequence=(0xFE | (0xFFFFFF00 & (0xFFFF0000 ^ cdef.nSequence_pad(genesis_cproof.outpoint)))))],
                          [CTxOut(42 << 1)])
        tx_cproof = TransferredColorProof(cdef, COutPoint(tx.GetHash(), 0), tx,
                                          {genesis_cproof.outpoint:genesis_cproof})

        tx_cproof.validate()

        # FIXME: need invalid tests too

