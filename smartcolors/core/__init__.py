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


class ColorDefHeader:
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

    def apply_kernel(self, tx, colored_outpoints_in):
        """Apply the color kernel to a given transaction

        colored_outpoints_in - ColorOutPoints for tx.vin

        Returns the new colored outpoints created by tx
        """

        amounts_out = [0] * len(tx.vout)
        prev_nSequence = None
        sum_color_in = 0
        for (i, colored_outpoint_in) in enumerate(colored_outpoints_in):
            if colored_outpoint_in not in tx.vin:
                raise Exception

            # All nSequence mappings must be identical
            if prev_nSequence is not None:
                if prev_nSequence != tx.vin[i].nSequence:
                    raise Exception
                prev_nSequence = tx.vin[i].nSequence

            # sum up color in
            #sum_color_in += <amount in>

        # sum up color going out
        #<fixme>

        # if color in != color out we have a problem!

        # return nSequence marked outputs


class AnnotatedColorDefHeader(ColorDefHeader):
    """Metadata bullshit goes here

    Actually, this stuff isn't consensus critical, so it'd go in another
    module.
    """
    company_name = 'blah blah blah'
    url = 'https://scam.coin'
    ceo = 'Yo Dawg'
    age_of_ceo = 16
    astrological_sign = 'cancer'


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


