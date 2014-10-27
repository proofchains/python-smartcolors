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

class ColorProofDb:
    """Database of ColorProofs

    Efficiently maintain a set of ColorDefs and ColorProofs relevant to known
    transactions.

    colordefs             - set of all ColorDefs in the database
    genesis_outpoints     - all known genesis outpoints: {COutPoint:set(ColorDef)}
    genesis_scriptPubKeys - all known genesis scriptPubKeys: {scriptPubKey:set(ColorDef)}
    colored_outpoints     - all known colored outpoints: {COutPoint:{ColorDef:set(ColorProof)}}
    """

    def __init__(self):
        self.colordefs = set()
        self.genesis_outpoints = {}
        self.genesis_scriptPubKeys = {}
        self.colored_outpoints = {}

    def addcolordef(self, colordef):
        """Add a color definition to the database"""

        # FIXME: add support for pruned definitions
        assert not colordef.is_pruned()

        if colordef not in self.colordefs:
            raise ValueError('colordef already in database')

        self.colordefs.add(colordef)

        for genesis_outpoint in colordef.genesis_outpoints:
            outpoint_colordef_set = self.genesis_outpoints.setdefault(genesis_outpoint.outpoint, set())

            # Ensures the colordef doesn't have the same outpoint multiple
            # times.
            assert colordef not in outpoint_colordef_set
            outpoint_colordef_set.add(genesis_outpoint)

        for genesis_scriptPubKey in colordef.genesis_scriptPubKeys:
            scriptPubKey_colordef_set = self.genesis_scriptPubKeys.setdefault(genesis_scriptPubKey, set())

            # Ensures the colordef doesn't have the same scriptPubKey multiple
            # times.
            assert colordef not in scriptPubKey_colordef_set
            scriptPubKey_colordef_set.add(genesis_scriptPubKey)


    def addtx(self, tx):
        """Add a transaction to the database"""

        # FIXME: what should happen if you addtx() twice?

        colored_outpoints = {}

        txid = tx.GetHash()

        # Check if any of the txouts are genesis points
        for i, txout in enumerate(tx.vout):
            outpoint = COutPoint(txid, i)

            # Check for genesis txouts
            for colordef in self.genesis_outpoints.get(outpoint, set()):
                # Slightly convoluted as we're adding an item to a set inside a
                # dict inside a dict, and all three of those things might not
                # exist yet.
                colorproof = GenesisOutPointColorProof(colordef, outpoint)
                self.colored_outpoints \
                    .setdefault(outpoint, {}) \
                    .setdefault(colordef, set()) \
                    .add(colorproof)

            # Genesis scriptPubKeys
            for colordef in self.genesis_scriptPubKeys.get(outpoint, set()):
                # Ditto
                colorproof = GenesisOutPointColorProof(colordef, outpoint)
                self.colored_outpoints \
                    .setdefault(outpoint, {}) \
                    .setdefault(colordef, set()) \
                    .add(colorproof)

        # Find colored inputs and sort the associated proofs by colordef
        prevout_proof_sets_by_colordef = {}
        for txin in tx.vin:
            try:
                colorproofs = self.colored_outpoints[txin.prevout]
            except KeyError:
                continue

            for colorproof in colorproofs:
                colordef_outpoints = prevout_proof_sets_by_colordef.setdefault(colorproof.colordef, {})
                outpoint_proofs = colordef_outpoints.setdefault(colorproof.outpoint, set())

                outpoint_proofs.add(colorproof)

        # With the prevout proofs sorted into colordef we can now apply the
        # appropriate color kernel for each one.
        for colordef, prevout_proof_sets_by_outpoint in prevout_proof_sets_by_colordef.items():
            assert prevout_proof_sets_by_outpoint # should never be empty

            # Create the color qty by txin prevout outpoint dict specific to
            # this colordef that the apply_kernel() function needs.
            color_qty_by_outpoint = {}

            # We've stored *sets* of ColorProofs for each txin prevout
            # outpoint; we want to pick just one proof out of each set. The
            # reason why it's a set is because there may be more than one way
            # to prove that a given outpoint is colored, for instance color may
            # have been both validly transferred to it, and because it has been
            # simultaneously declared as colored by the color definition.
            #
            # In addition the quantity of color proven may be different in each
            # case. For now we'll just throw an assertion if that is detected,
            # but in the future it may be desirable to change that behavior.

            # The dict mapping txin prevout outpoint to ColorProof that we'll
            # give to apply_kernel()
            prevout_proofs = {}

            for outpoint, prevout_proof_set in prevout_proof_sets_by_outpoint.items():
                assert prevout_proof_set # should never be empty

                # Sort the set of available proofs for this outpoint in priority order:
                # genesis outpoints > scriptPubKey > transferred color > anything else
                def proof_priority_key(proof):
                    if isinstance(proof, GenesisOutPointColorProof):
                        return 0
                    elif isinstance(proof, GenesisScriptPubKeyColorProof):
                        return 1
                    elif isinstance(proof, TransferredColorProof):
                        return 2
                    else:
                        return 3

                best_proof = next(iter(sorted(prevout_proofs, key=proof_priority_key)))

                # Make sure that the color quantities proven by all proofs are
                # identical. (for now)
                assert all(prevout_proof.qty == best_proof.qty for prevout_proof in prevout_proof_set)

                prevout_proofs[outpoint] = best_proof

            # Now we can finally apply the kernel and start creating proofs for
            # the color movement for each colored output
            color_qty_by_outpoint = {outpoint:colorproof.qty for outpoint, colorproof in prevout_proofs.items()}
            for i, qty in colordef.apply_kernel(tx, color_qty_by_outpoint):
                colorproof = TransferredColorProof(colordef, COutPoint(txid, i), tx, prevout_proofs)
                self.colored_outpoints \
                    .setdefault(outpoint, {}) \
                    .setdefault(colordef, set()) \
                    .add(colorproof)
