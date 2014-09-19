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


class GenesisPointDef(bitcoin.core.serialize.ImmutableSerializable):
    """Definition of a specific genesis outpoint

    Base class
    """
    __slots__ = []

    TYPE = None

    CLASSES_BY_TYPE = {}

    def stream_serialize(self, f):
        f.write(self.TYPE)

    @classmethod
    def stream_deserialize(cls, f):
        point_type = bitcoin.core.serialize.ser_read(f, 1)

        try:
            cls = cls.CLASSES_BY_TYPE[point_type]
        except KeyError:
            raise bitcoin.core.serialize.SerializationError(
                    'GenesisPointDef deserialize: bad genesis point type %r' % point_type)

        return cls._GenesisPointDef_stream_deserialize(f)

def make_GenesisPointDef_subclass(cls):
    GenesisPointDef.CLASSES_BY_TYPE[cls.TYPE] = cls
    return cls

@make_GenesisPointDef_subclass
class TxOutGenesisPointDef(GenesisPointDef):
    """Genesis outpoint defined by a specific COutPoint"""
    __slots__ = ['outpoint']

    TYPE = b'\x01'

    def __init__(self, outpoint):
        object.__setattr__(self, 'outpoint', outpoint)

    @classmethod
    def _GenesisPointDef_stream_deserialize(cls, f):
        outpoint = COutPoint.stream_deserialize(f)
        return cls(outpoint)

    def stream_serialize(self, f):
        super(TxOutGenesisPointDef, self).stream_serialize(f)
        self.outpoint.stream_serialize(f)

@make_GenesisPointDef_subclass
class ScriptPubKeyGenesisPointDef(GenesisPointDef):
    """Generic genesis outpoint defined as a spend of a specific scriptPubKey

    Note that to prove this requires having the previous transaction available.
    (can be avoided by verifying signatures)
    """
    __slots__ = ['scriptPubKey']
    TYPE = b'\x02'

    # FIXME: add below
    # max_height = int # maximum block height the scriptPubKey is valid for

    def __init__(self, scriptPubKey):
        object.__setattr__(self, 'scriptPubKey', scriptPubKey)

    @classmethod
    def _GenesisPointDef_stream_deserialize(cls, f):
        scriptPubKey = bitcoin.core.serialize.BytesSerializer.stream_deserialize(f)
        scriptPubKey = bitcoin.core.script.CScript(scriptPubKey)
        return cls(scriptPubKey)

    def stream_serialize(self, f):
        super(ScriptPubKeyGenesisPointDef, self).stream_serialize(f)
        bitcoin.core.serialize.BytesSerializer.stream_serialize(self.scriptPubKey, f)


class ColorDef(bitcoin.core.serialize.ImmutableSerializable):
    """The low-level definition of a color

    Commits to all valid genesis points for this color in a merkle tree. This
    lets even very large color definitions be used efficiently by SPV clients.
    """
    __slots__ = ['version', 'prevdef_hash', 'genesis_set']

    # Previous version of this color definition
    prev_header_hash = 'uint256'

    def __init__(self, genesis_set=None, prevdef_hash=b'\x00'*32):
        if genesis_set is None:
            genesis_set = set()
        genesis_set = set(genesis_set)
        object.__setattr__(self, 'genesis_set', genesis_set)
        object.__setattr__(self, 'prevdef_hash', prevdef_hash)

    def calc_color_transferred(self, txin, color_in, color_out, tx):
        """Calculate the color transferred by a specific txin

        txin      - txin (CTxIn)
        color_in  - Color qty of input (int)
        color_out - Color qty on outputs
        tx        - Transaction

        color_out is modified in-place.
        """
        remaining_color_in = color_in

        # Which outputs the color in is being sent to is specified by
        # nSequence.
        for j in range(min(len(tx.vout), 32)):
            # An output is marked as colored if the corresponding bit
            # in nSequence is set to one. This is chosen to allow
            # standard transactions with standard-looking nSquence's to
            # move color.
            if remaining_color_in and (txin.nSequence >> j) & 0b1 == 1:
                # Mark the output as being colored if it hasn't been
                # already.
                if color_out[j] is None:
                    color_out[j] = 0

                # Color is allocated to outputs "bucket-style", where
                # each colored input adds to colored outputs until the
                # output is "full". As color_out is modified in place the
                # allocation is stateful - a previous txin can change where the
                # next txin sends its quantity of color.
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

    def apply_kernel(self, tx, color_in):
        """Apply the color kernel to a transaction

        The kernel only tracks the movement of color from input to output; the
        creation of genesis txouts is handled separately.

        tx       - The transaction
        color_in - Color in by txin idx

        Return a list of amount of color out indexed by vout index. Colored
        outputs are a non-zero integers, uncolored outputs are None.
        """

        # FIXME: need a top-leve overview of the thinking behind nSequence

        color_out = [None] * len(tx.vout)

        for (i, txin) in enumerate(tx.vin):
            if color_in[i] is None:
                # Input not colored
                continue

            else:
                self.calc_color_transferred(txin, color_in[i], color_out, tx)

        return color_out

    def prune(self, relevant_genesis_outs):
        pruned_genesis_set = self.genesis_set.prove_contains(relevant_genesis_outs)

        # Note how we allow subclasses to work!
        return self.__class__(self.prevdef_hash, pruned_genesis_set)


class ColorProof:
    """Proof that one or more outpoint's are a certain color

    Contains all transactions required to prove all relevant color moves back
    to the genesis points. Also manages updates to the proof as
    blocks/transactions are added/removed.
    """

    __slots__ = ['version', 'colordef', 'all_outputs', 'unspent_outputs', 'txs']

    def __init__(self, colordef, txs=()):
        self.colordef = colordef

        self.all_outputs = {}
        self.unspent_outputs = {}

        self.txs = []
        for tx in txs:
            self.addtx(tx)

    def addtx(self, tx):
        """Add a new tx to the proof

        self.outputs will be updated
        """

        new_colored_outs = set()

        # Check tx outputs for genesis points defined by outpoint
        for i in range(len(tx.vout)):
            genesis_point = TxOutGenesisPointDef(COutPoint(tx.GetHash(), i))

            if genesis_point in self.colordef.genesis_set:
                color_qty = remove_msbdrop_value_padding(tx.vout[i].nValue)
                self.all_outputs[genesis_point.outpoint] = color_qty
                self.unspent_outputs[genesis_point.outpoint] = color_qty

        # Check inputs for spends of genesis scriptPubKeys
        if False:
            for txin in tx.vin:
                prevout = txin.prevout

                try:
                    prevtx = self.txs[prevout.hash]
                except IndexError:
                    # Can't prove anything without the previous tx, so continue
                    continue

                if (prevout in self.genesis_set # defined directly by COutPoint
                    or prevtx.vout[prevout.n].scriptPubKey in self.genesis_set): # defined by scriptPubKey

                    new_colored_out = ColoredOutPoint.from_tx(prevtx, prevout)

                    # Add the new colored output to the known and unspent output
                    # sets. The output may in fact already be in these sets as an
                    # output can be colored by fiat by the issuer and
                    # simultaneously be colored by virtue of being a descendent of
                    # a genesis output.
                    self.all_outputs.add(new_colored_out)
                    self.unspent_outputs.add(new_colored_out)

        # Apply the kernel.
        #
        # FIXME: Consider how addtx() should behave if we apply it to the same
        # tx twice. If all colored inputs are known and we apply the same
        # transaction twice the inputs to that transaction will be missing from
        # the unspent outputs set and the kernel will do nothing; no change.
        # However if only some colored inputs are known, addtx() is called,
        # then more colored inputs become known, the second addtx() could end
        # up adding the same output to the unspent_outputs list twice, with the
        # second time having a different amount of color.
        txhash = tx.GetHash()

        # FIXME: apply_kernel should probably just take the unspent_outputs directly
        color_in = [self.unspent_outputs.get(txin.prevout, None) for txin in tx.vin]
        color_qtys = self.colordef.apply_kernel(tx, color_in)

        for i, color_qty in enumerate(color_qtys):
            if color_qty is not None:
                outpoint = COutPoint(txhash, i)

                self.all_outputs[outpoint] = color_qty
                self.unspent_outputs[outpoint] = color_qty

        # remove spent colored outputs from unspent
        for txin in tx.vin:
            self.unspent_outputs.pop(txin.prevout, None)

    def removetx(self, tx):
        """Remove a transaction from the proof

        Other transactions may be removed as well
        """

        # FIXME: Fair amount of thought involved in getting this right; easiest
        # approach would be to just re-addtx() all txs in order for a
        # ref-implementation to write tests against.
        raise NotImplementedError

    def prove_outputs(self, outputs):
        """Prove a subset of outputs

        Returns a new ColorProof
        """

        genesis_outputs = set()
        outputs = set(outputs)
        relevant_txs = insertion_ordered_set()

        while outputs:
            next_outputs = set()

            for output in outputs:
                tx = self.txs[output]

                relevant_txs.add(tx)

                for txin in tx:
                    if txin is a_genesis_output:
                        genesis_outputs.add(txin.prevout)

                        # may need to add supporting txs, e.g. for scriptPubKey-based geneis outputs

                    else:
                        # otherwise keep backtracking
                        next_outputs.add(txin.prevout)

            outputs = next_outputs

        # We can prune our color def to only include the genesis outputs we
        # found.
        pruned_colordef = self.colordef.prune(genesis_outputs)

        # Note how this ensures subclasses work!
        return self.__class__(pruned_colordef, relevant_txs)

    def create_bloom_filter(self):
        """Return a bloom filter that will match on transactions spending colored outputs proven

        Use self.addtx() to add the transactions to the proof.
        """
        raise NotImplementedError

