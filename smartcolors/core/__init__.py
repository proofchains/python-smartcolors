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

import os
import struct

import bitcoin.core.serialize
import proofmarshal
import proofmarshal.merbinnertree

from bitcoin.core import COutPoint, CTransaction, b2lx, x, b2x, Hash
from bitcoin.core.script import CScript


def remove_msbdrop_value_padding(padded_nValue):
    """Remove MSB-Drop nValue padding

    Returns unpadded nValue
    """
    if padded_nValue & 0b1 == 0:
        # MSB padding was not used
        return padded_nValue >> 1

    elif padded_nValue & 0b1 == 1:
        # Test against increasingly smaller msb_masks until we find the MSB set
        # to 1
        for i in range(63, 0, -1):
            msb_mask = 1 << i
            if msb_mask & padded_nValue:
                return (padded_nValue & ~msb_mask) >> 1

        # Degenerate case: padded_nValue == 0b1 and unpadded value == 0
        assert padded_nValue >> 1 == 0
        return 0

    else:
        raise TypeError('LSB of padded nValue is neither 1 nor 0')


# Note that this function is *not* consensus critical; maybe should be moved
# elsewhere?
def add_msbdrop_value_padding(unpadded_nValue, minimum_nValue=0):
    """Pad a nValue using MSB-Drop method

    minimum_nValue - minimum allowed nValue

    Returns padded nValue
    """
    if not (0 <= minimum_nValue <= 2**64-1):
        raise ValueError("Minimum nValue out of range")

    # Technically this range could be larger, but then "needs padding" and
    # "doesn't need padding" cases would have to be handled separately
    if not (0 <= unpadded_nValue <= 2**62-1):
        raise ValueError("Unpadded nValue out of range")

    if (unpadded_nValue << 1) >= minimum_nValue:
        # No padded needed!
        return unpadded_nValue << 1

    else:
        i = 0
        while (1 << i) <  (unpadded_nValue << 1) | 0b1:
            i += 1
        while (1 << i) | (unpadded_nValue << 1) | 0b1 < minimum_nValue:
            i += 1

        return (1 << i) | (unpadded_nValue << 1) | 0b1

class GenesisOutPointsMerbinnerTree(proofmarshal.merbinnertree.MerbinnerTree):
    HASH_HMAC_KEY = x('d8497e1258c3f8e747341cb361676cee')

    key_serialize = lambda self, ctx, key: ctx.write_bytes('key', key.serialize(), 36)
    key_deserialize = lambda self, ctx: COutPoint.deserialize(ctx.read_bytes('key', 36))

    value_serialize = lambda self, ctx, value: ctx.write_varuint('value', value)
    value_deserialize = lambda self, ctx: ctx.read_varuint('value')

    key_gethash = lambda self, key: key.GetHash()
    value_getsum = lambda self, value: value

    sum_serialize = lambda self, ctx, sum: ctx.write_varuint('sum', sum)


class GenesisScriptPubKeysMerbinnerTree(proofmarshal.merbinnertree.MerbinnerTree):
    HASH_HMAC_KEY = x('d431b155684582c6e0eef8b38d62321e')

    key_serialize = lambda self, ctx, key: ctx.write_bytes('key', key)
    key_deserialize = lambda self, ctx: CScript(ctx.read_bytes('key'))

    value_serialize = lambda self, ctx, value: None
    value_deserialize = lambda self, ctx: None

    key_gethash = lambda self, key: Hash(key)


class ColorDef(proofmarshal.ImmutableProof):
    """The low-level definition of a color

    Commits to all valid genesis points for this color in a merkle tree. This
    lets even very large color definitions be used efficiently by SPV clients.
    """
    __slots__ = ['version',
                 'birthdate_blockheight',
                 'stegkey',
                 'genesis_outpoints',
                 'genesis_scriptPubKeys',
                 '_cached_hash',
                ]

    HASH_HMAC_KEY = x('1d8801c1323b4cc5d1b48b289d35aad0')

    VERSION = 1
    STEGKEY_LEN = 16

    def __init__(self, *,
                 genesis_outpoints=None,
                 genesis_scriptPubKeys=None,
                 birthdate_blockheight=0,
                 stegkey=None):

        if stegkey is None:
            stegkey = os.urandom(self.STEGKEY_LEN)
        assert len(stegkey) == self.STEGKEY_LEN

        # FIXME: should be a merbinner tree
        if genesis_outpoints is None:
            genesis_outpoints = {}
        genesis_outpoints = GenesisOutPointsMerbinnerTree(genesis_outpoints)

        if genesis_scriptPubKeys is None:
            genesis_scriptPubKeys = set()
        genesis_scriptPubKeys = {scriptPubKey:None for scriptPubKey in genesis_scriptPubKeys}
        genesis_scriptPubKeys = GenesisScriptPubKeysMerbinnerTree(genesis_scriptPubKeys)

        object.__setattr__(self, 'genesis_outpoints', genesis_outpoints)
        object.__setattr__(self, 'genesis_scriptPubKeys', genesis_scriptPubKeys)
        object.__setattr__(self, 'birthdate_blockheight', birthdate_blockheight)
        object.__setattr__(self, 'stegkey', stegkey)

    def _ctx_deserialize(self, ctx):
        version = ctx.read_varuint('version')
        if version != self.VERSION:
            raise SerializationError('wrong version: got %d; expected %d' % (version, self.VERSION))

        birthdate_blockheight = ctx.read_varuint('birthdate_blockheight')
        object.__setattr__(self, 'birthdate_blockheight', birthdate_blockheight)

        stegkey = ctx.read_bytes('stegkey', self.STEGKEY_LEN)
        object.__setattr__(self, 'stegkey', stegkey)

        genesis_outpoints = ctx.read_obj('genesis_outpoints', GenesisOutPointsMerbinnerTree)
        object.__setattr__(self, 'genesis_outpoints', genesis_outpoints)

        genesis_scriptPubKeys = ctx.read_obj('genesis_scriptPubKeys', GenesisScriptPubKeysMerbinnerTree)
        object.__setattr__(self, 'genesis_scriptPubKeys', genesis_scriptPubKeys)

    def _ctx_serialize(self, ctx):
        ctx.write_varuint('version', self.VERSION)
        ctx.write_varuint('birthdate_blockheight', self.birthdate_blockheight)
        ctx.write_bytes('stegkey', self.stegkey, self.STEGKEY_LEN)
        ctx.write_obj('genesis_outpoints', self.genesis_outpoints)
        ctx.write_obj('genesis_scriptPubKeys', self.genesis_scriptPubKeys)

    def nSequence_pad(self, outpoint):
        """Derive the nSequence pad from a given outpoint

        Returns an int that can be XORed with the desired value to get
        nSequence.
        """
        # Magic: 916782d006cd95e3d24b698df0aeb28e
        b = b'\x91\x67\x82\xd0\x06\xcd\x95\xe3\xd2\x4b\x69\x8d\xf0\xae\xb2\x8e' \
            + self.stegkey + outpoint.hash + struct.pack('<I', outpoint.n)
        pad = bitcoin.core.serialize.Hash(b)[0:4]
        return struct.unpack('<I', pad)[0]

    def calc_color_transferred(self, txin, color_qty_in, color_qtys_out, tx):
        """Calculate the color transferred by a specific txin

        txin           - txin (CTxIn)
        color_qty_in   - Color qty of input txin (int)
        color_qtys_out - Color qty on outputs (list of ints)
        tx             - Transaction

        color_out is modified in-place.
        """
        remaining_color_qty_in = color_qty_in

        # Which outputs the color in is being sent to is specified by
        # nSequence.

        # bits 6-0 are used to determine what kernel to use
        kernel_num = txin.nSequence & 0x7F

        # bit #7 turns nSequence decryption on and off; important in case a
        # future CHECKSIG or something can create signatures that don't sign
        # the prevout
        decrypted_nSequence = txin.nSequence
        if txin.nSequence & 0b10000000:
            decrypted_nSequence ^= self.nSequence_pad(txin.prevout)

        if kernel_num == 0x7F:
            # PUSHDATA routing
            #
            # Gets 0xFF so it can hide amongst standard transactions. Other
            # three bytes are XORed with per-colordef stegkey, which means even
            # if they're all 1's you get per-color distingishment
            raise NotImplementedError

        elif kernel_num == 0x7E:
            # nSequence routing
            #
            # One less than max-int, again to hide amongst standard
            # transactions. (proposed "always-use-nLockTime" standard)

            # bits 15-8 are qty shift (exponent)
            qty_shift = (decrypted_nSequence >> 8) & 0xFF

            assert qty_shift == 0 # FIXME

            # bits 31-16 are colored/uncolored data
            colored_bitfield = (decrypted_nSequence >> 16) & 0xFFFF
            for j in range(min(len(tx.vout), 16)):
                # An output is marked as colored if the corresponding bit
                # in nSequence is set to one. This is chosen to allow
                # standard transactions with standard-looking nSquence's to
                # move color.
                if remaining_color_qty_in and (colored_bitfield >> j) & 0b1 == 1:
                    # Mark the output as being colored if it hasn't been
                    # already.
                    if color_qtys_out[j] is None:
                        color_qtys_out[j] = 0

                    # Color is allocated to outputs "bucket-style", where each
                    # colored input adds to colored outputs until the output is
                    # "full". As color_qtys_out is modified in place the allocation
                    # is stateful - a previous txin can change where the next txin
                    # sends its quantity of color.
                    max_color_qty_out = remove_msbdrop_value_padding(tx.vout[j].nValue)
                    color_transferred = min(remaining_color_qty_in, max_color_qty_out - color_qtys_out[j])
                    color_qtys_out[j] += color_transferred
                    remaining_color_qty_in -= color_transferred

                    assert color_transferred >= 0
                    assert remaining_color_qty_in >= 0

        else:
            raise NotImplementedError

        # Any remaining color that hasn't been sent to an output by the txin is
        # simply destroyed. This ensures all color transfers happen explicitly,
        # rather than implicitly, which may be useful in the future to reduce
        # proof sizes for large transactions.

    def apply_kernel(self, tx, color_qty_by_outpoint):
        """Apply the color kernel to a transaction

        The kernel only tracks the movement of color from input to output; the
        creation of genesis txouts is handled separately.

        tx                    - The transaction
        color_qty_by_outpoint - Dict-like of color qty by outpoint

        Return a list of amount of color out indexed by vout index. Colored
        outputs are a non-zero integers, uncolored outputs are None.

        FIXME: describe behavior if spent outpoints are in
               color_qty_by_outpoint
        """

        # FIXME: need a top-level overview of the thinking behind nSequence

        color_qtys_out = [None] * len(tx.vout)

        for txin in tx.vin:
            try:
                color_qty_in = color_qty_by_outpoint[txin.prevout]
            except KeyError:
                color_qty_in = None

            if color_qty_in is None:
                # Input not colored
                continue

            else:
                self.calc_color_transferred(txin, color_qty_in, color_qtys_out, tx)

        return color_qtys_out

    def is_pruned(self):
        return False

class ColorProofValidationError(Exception):
    pass

class ColorProof:
    """Prove that a specific outpoint is colored"""

    __slots__ = ['outpoint', 'colordef']

    def _validate(self):
        raise NotImplementedError

    def validate(self):
        """Validate the proof"""

        remaining_proofs = (self,)
        while remaining_proofs:
            next_remaining_proofs = []

            for proof in remaining_proofs:
                next_remaining_proofs.extend(proof._validate())

            remaining_proofs = next_remaining_proofs


class GenesisOutPointColorProof(ColorProof):
    """Prove that an outpoint is colored because it is a genesis outpoint"""
    __slots__ = []

    def __init__(self, colordef, outpoint):
        self.outpoint = outpoint
        self.colordef = colordef

    @property
    def qty(self):
        return self.colordef.genesis_outpoints[self.outpoint]

    def _validate(self):
        if self.outpoint not in self.colordef.genesis_outpoints:
            raise ColorProofValidationError('outpoint not in genesis outpoints')

        return ()

class GenesisScriptPubKeyColorProof(ColorProof):
    """Prove that an outpoint is colored because it is a genesis scriptPubKey"""
    __slots__ = ['tx']


    def __init__(self, colordef, outpoint, tx):
        self.outpoint = outpoint
        self.colordef = colordef
        self.tx = tx

    @property
    def qty(self):
        # FIXME: add/remove msbdrop padding should be part of the colordef to
        # make it more generic
        return remove_msbdrop_value_padding(self.tx.vout[self.outpoint.n].nValue)

    def _validate(self):
        if self.tx.GetHash() != self.outpoint.hash or not (0 <= self.outpoint.n < len(self.tx.vout)):
            raise ColorProofValidationError('outpoint does not match transaction')

        if self.tx.vout[self.outpoint.n] not in self.colordef.genesis_scriptPubKeys:
            raise ColorProofValidationError('scriptPubKey not a genesis scriptPubKey')

        return ()

class TransferredColorProof(ColorProof):
    """Prove that an outpoint is colored because color was transferred to it"""

    __slots__ = ['tx', 'prevout_proofs',
                 '__cached_qty']

    def __init__(self, colordef, outpoint, tx, prevout_proofs):
        self.outpoint = outpoint
        self.colordef = colordef
        self.tx = tx
        self.prevout_proofs = prevout_proofs

    def calc_qty(self):
        """Calculate the quantity of color assigned to this outpoint"""
        color_qty_by_outpoint = {prevout:colorproof.qty for prevout, colorproof in self.prevout_proofs.items()}

        color_qty_out = self.colordef.apply_kernel(self.tx, color_qty_by_outpoint)

        try:
            qty = color_qty_out[self.outpoint.n]
        except IndexError:
                raise ColorProofValidationError('outpoint does not match transaction; n out of bounds')

        if qty is None:
            raise ColorProofValidationError('no color assigned to outpoint')
        else:
            return qty

    @property
    def qty(self):
        try:
            return self.__cached_qty
        except AttributeError:
            self.__cached_qty = self.calc_qty()
            return self.__cached_qty

    def _validate(self):
        yield from self.prevout_proofs.values()

        if self.tx.GetHash() != self.outpoint.hash:
            raise ColorProofValidationError('outpoint does not match transaction; wrong txid')

        self.calc_qty()

