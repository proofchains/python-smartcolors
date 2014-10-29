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
import smartcolors.core.util

from bitcoin.core import COutPoint, CTransaction, b2lx
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


class ColorDef(bitcoin.core.serialize.ImmutableSerializable):
    """The low-level definition of a color

    Commits to all valid genesis points for this color in a merkle tree. This
    lets even very large color definitions be used efficiently by SPV clients.
    """
    __slots__ = ['version',
                 'prevdef_hash',
                 'genesis_outpoints',
                 'genesis_scriptPubKeys',
                 'birthdate_blockheight',
                 'stegkey',
                ]

    VERSION = 0

    def __init__(self, *,
                 genesis_outpoints=None,
                 genesis_scriptPubKeys=None,
                 prevdef_hash=b'\x00'*32,
                 version=0,
                 birthdate_blockheight=0,
                 stegkey=None):
        object.__setattr__(self, 'version', version)

        if stegkey is None:
            stegkey = os.urandom(16)
        assert len(stegkey) == 16

        # FIXME: should be a merbinner tree
        if genesis_outpoints is None:
            genesis_outpoints = {}
        genesis_outpoints = dict(genesis_outpoints)

        if genesis_scriptPubKeys is None:
            genesis_scriptPubKeys = {}
        genesis_scriptPubKeys = set()

        object.__setattr__(self, 'genesis_outpoints', genesis_outpoints)
        object.__setattr__(self, 'genesis_scriptPubKeys', genesis_scriptPubKeys)
        object.__setattr__(self, 'prevdef_hash', prevdef_hash)
        object.__setattr__(self, 'birthdate_blockheight', birthdate_blockheight)
        object.__setattr__(self, 'stegkey', stegkey)

    @classmethod
    def stream_deserialize(cls, f):
        version = struct.unpack(b"<I", bitcoin.core.serialize.ser_read(f,4))[0]
        if version != cls.VERSION:
            raise SerializationError('wrong version: got %d; expected %d' % (version, cls.VERSION))

        birthdate_blockheight = struct.unpack(b"<I", bitcoin.core.serialize.ser_read(f,4))[0]

        prevdef_hash = bitcoin.core.serialize.ser_read(f, 32)

        genesis_outpoints = bitcoin.core.serialize.VectorSerializer.stream_deserialize(GenesisPointDef, f)
        return cls(genesis_outpoints=genesis_outpoints, prevdef_hash=prevdef_hash,
                   version=version, birthdate_blockheight=birthdate_blockheight)

    def stream_serialize(self, f):
        f.write(struct.pack(b'<I', self.version))
        f.write(struct.pack(b'<I', self.birthdate_blockheight))
        assert len(self.prevdef_hash) == 32
        f.write(self.prevdef_hash)
        sorted_genesis_outpoints = sorted(self.genesis_outpoints) # to get consistent hashes
        # FIXME: get serialization class right
        bitcoin.core.serialize.VectorSerializer.stream_serialize(TxOutGenesisPointDef, sorted_genesis_outpoints, f)

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
        decrypted_nSequence = self.nSequence_pad(txin.prevout) ^ txin.nSequence
        for j in range(min(len(tx.vout), 32)):
            # An output is marked as colored if the corresponding bit
            # in nSequence is set to one. This is chosen to allow
            # standard transactions with standard-looking nSquence's to
            # move color.
            if remaining_color_qty_in and (decrypted_nSequence >> j) & 0b1 == 1:
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
        color_qty_by_outpoint = {}

        for prevout, colorproof in self.prevout_proofs.items():
            color_qty_by_outpoint[prevout] = colorproof.qty
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

