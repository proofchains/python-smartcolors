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

class Test_ColorDefHeader_kernel(unittest.TestCase):
    def make_color_tx(self, input_nsequences, output_amounts):
        """Make a test transaction"""
        vin = [CTxIn(nSequence=nSequence) for nSequence in input_nsequences]
        vout = [CTxOut(add_msbdrop_value_padding(nValue, 0)) for nValue in output_amounts]
        return CTransaction(vin, vout)

    def test_no_colored_inputs(self):
        """Degenerate case of no colored inputs or outputs"""
        hdr = ColorDefHeader()
        tx = self.make_color_tx([0], [0])
        color_out = hdr.apply_kernel(tx, (None,))
        self.assertEqual(color_out, [None])

    def test_one_to_one_exact(self):
        """One colored input to one colored output, color_in == max_out"""
        hdr = ColorDefHeader()
        tx = self.make_color_tx([0b1], [1])
        color_out = hdr.apply_kernel(tx, (1,))
        self.assertEqual(color_out, [1])

    def test_one_to_one_less_than_max(self):
        """One colored input to one colored output, color_in < max_out"""
        hdr = ColorDefHeader()
        tx = self.make_color_tx([0b1], [10])
        color_out = hdr.apply_kernel(tx, (1,))
        self.assertEqual(color_out, [1])

    def test_one_to_one_more_than_max(self):
        """One colored input to one colored output, color_in > max_out"""
        hdr = ColorDefHeader()
        tx = self.make_color_tx([0b1], [1])
        color_out = hdr.apply_kernel(tx, (2,))
        self.assertEqual(color_out, [1])

    def test_one_to_two_exact(self):
        """One colored input to two colored outputs, color_in == max_out"""
        hdr = ColorDefHeader()
        tx = self.make_color_tx([0b11], [1, 2])
        color_out = hdr.apply_kernel(tx, (3,))
        self.assertEqual(color_out, [1, 2])

    def test_one_to_two_less_than_max(self):
        """One colored input to two colored outputs, color_in < max_out"""
        hdr = ColorDefHeader()

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
        hdr = ColorDefHeader()

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
        hdr = ColorDefHeader()

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
        hdr = ColorDefHeader()

        tx = self.make_color_tx([0b10, 0b01], [2, 3, 4])
        color_out = hdr.apply_kernel(tx, (1,3))
        self.assertEqual(color_out, [2, 1, None])

    def test_multiple_to_one(self):
        hdr = ColorDefHeader()

        tx = self.make_color_tx([0b1, 0b1, 0b1, 0b1, 0b1], [1+2+3+4+5])
        color_out = hdr.apply_kernel(tx, (1,2,3,4,5))
        self.assertEqual(color_out, [1+2+3+4+5])

        tx = self.make_color_tx([0b11, 0b11, 0b11, 0b11, 0b11], [1+2+3+4+5, 100])
        color_out = hdr.apply_kernel(tx, (1,2,3,4,5))
        self.assertEqual(color_out, [1+2+3+4+5, 0])
