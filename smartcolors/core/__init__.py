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

import bitcoin.core.serialize

from bitcoin.core import COutPoint, CTransaction
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
def add_msbdrop_value_padding(unpadded_nValue, minimum_nValue):
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


class ColoredOutPoint(COutPoint):
    """An outpoint with color info"""

    # amount of color tokens
    amount = int

class BaseGenesisPointDef:
    """Definition of a specific genesis outpoint

    Base class
    """

class TxOutGenesisPointDef:
    """Genesis outpoint defined by a specific COutPoint"""
    outpoint = COutPoint


class scriptPubKeyGenesisPointDef:
    """Generic genesis outpoint defined as a spend of a specific scriptPubKey

    Note that to prove this requires having the previous transaction available.
    (can be avoided by verifying signatures)
    """
    scriptPubKey = CScript
    max_height = int # maximum block height the scriptPubKey is valid for


class ColorDefHeader(bitcoin.core.serialize.ImmutableSerializable):
    """Header for the low-level definition of a color

    The header commits to all valid genesis points for this color in a merkle
    tree. This lets even very large color definitions be used efficiently by
    SPV clients.
    """

    # Previous version of this color definition
    prev_header_hash = 'uint256'

    # Merkle root of all genesis point definitions valid for this color.
    #
    # TODO: should this be a merkle-sum tree instead? Combined with a key we
    # could have colors definitions where what shares have been issued and to
    # whome is actually totally private information, yet there is no way for
    # the issuer to lie about how many shares have been issued is something
    # they can't lie about. (modulo scriptPubKey-issuance that is)
    genesis_point_merkle_root = 'uint256'

    def calc_color_transferred(self, txin, color_in, tx):
        """Calculate the color transferred by a specific txin

        txin     - txin (CTxIn)
        color_in - Amount of color present (int)
        tx       - Transaction

        Returns a list of color out indexed by vout index. Colored outputs are
        a non-negative int, uncolored outptus are None.
        """
        color_out = [None] * len(tx.vout)
        remaining_color_in = color_in

        # Which outputs the color in is being sent to is specified by
        # nSequence.
        for j in range(min(len(tx.vout), 32)):
            # An output is marked as colored if the corresponding bit
            # in nSequence is set to one. This is chosen to allow
            # standard transactions with standard-looking nSquence's to
            # move color.
            if (txin.nSequence >> j) & 0b1 == 1:
                # Mark the output as being colored if it hasn't been
                # already.
                if color_out[j] is None:
                    color_out[j] = 0

                # Color is allocated to outputs "bucket-style", where
                # each colored input adds to colored outputs until the
                # output is "full".
                max_color_out = remove_msbdrop_value_padding(tx.vout[j].nValue)
                color_transferred = min(remaining_color_in, max_color_out - color_out[j])
                color_out[j] += color_transferred
                remaining_color_in -= color_transferred

                assert color_transferred >= 0
                assert remaining_color_in >= 0

        # Any remaining color that hasn't been sent to an output by the
        # txin is simply destroyed. This ensures all color transfers
        # happen explicitly, rather than implicitly, which may be
        # useful in the future to reduce proof sizes for large
        # transactions.
        return color_out

    def apply_kernel(self, tx, color_in):
        """Apply the color kernel to a transaction

        The kernel only tracks the movement of color from input to output; the
        creation of genesis txouts is handled separately.

        tx       - The transaction
        color_in - Color in by txin idx

        Return a list of amount of color out indexed by vout index. Colored
        outputs are a >= 0 integer, uncolored outputs are None.
        """

        color_out = [None] * len(tx.vout)

        for (i, txin) in enumerate(tx.vin):
            if color_in[i] is None:
                # Input not colored
                continue

            else:
                for i, amount in enumerate(self.calc_color_transferred(txin, color_in[i], tx)):
                    if amount is not None:
                        if color_out[i] is None:
                            color_out[i] = 0
                        color_out[i] += amount

        return color_out


class MerkleColorDef(ColorDefHeader):
    """Full color definition

    Contains actual genesis points, up to and including all of them, as well as
    whatever parts of the merkle tree are needed to recompute the merkle root.

    Encoding should be such that a MerkleColorDef can prove a single genesis
    point efficently, removing the need for a MerkleGenesisDef.
    """

    genesis_points = []

    # will need some scheme similar to CMerkleBlock's - can we avoid the
    # preimage attack that Satoshi's block hashing algorithm has?
    #
    # Should we use a radix tree instead with ordering? Would be useful to be
    # able to prove that a given outpoint/scriptPubKey was *not* colored,
    # although note how the key would have to be H(genesispoint.scriptPubKey)
    # rather than H(genesispoint.serialize())
    # bits_or_something = dunno yet

    def create_bloom_filter(self):
        """Return a bloom filter that will match on the genesis_points"""


class ColorProof:
    """Proof that one or more outpoint's are a certain color

    Contains all transactions required to prove all relevant color moves back
    to the genesis points. Also manages updates to the proof as
    blocks/transactions are added/removed.
    """

    # The color definition we're trying to prove
    # colored = MerkleColorDef

    # Transactions in the proof
    # txs = (CMerkleTx,)

    # Current proven outputs
    # outputs = (ColoredOutpoint,)

    def addtx(self, tx):
        """Add a new tx to the proof

        self.outputs will be updated
        """

    def removetx(self, tx):
        """Remove a transaction from the proof

        Other transactions may be removed as well
        """

    def prove_outputs(self, outputs):
        """Prove a subset of outputs

        Returns a new ColorProof
        """

    def create_bloom_filter(self):
        """Return a bloom filter that will match on transactions spending colored outputs proven

        Use self.addtx() to add the transactions to the proof.
        """

