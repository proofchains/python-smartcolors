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
import os
import struct

import bitcoin.core.serialize

from bitcoin.core import COutPoint, CTransaction, b2lx, Hash
from bitcoin.core.script import CScript

from smartcolors.core import (
        GenesisOutPointColorProof,
        GenesisScriptPubKeyColorProof,
        TransferredColorProof
)

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

        if colordef in self.colordefs:
            return # already added, so we can stop now

        self.colordefs.add(colordef)

        for genesis_outpoint, qty in colordef.genesis_outpoints.items():
            outpoint_colordef_set = self.genesis_outpoints.setdefault(genesis_outpoint, set())

            # Ensures the colordef doesn't have the same outpoint multiple
            # times.
            assert colordef not in outpoint_colordef_set
            outpoint_colordef_set.add(colordef)

            # Genesis outpoints don't need the transactions themselves to be
            # proven, so create the corresponding proofs and add them to the
            # colored_outpoints
            colorproof = GenesisOutPointColorProof(colordef, genesis_outpoint)
            self.colored_outpoints \
                .setdefault(genesis_outpoint, {}) \
                .setdefault(colordef, set()) \
                .add(colorproof)

        for genesis_scriptPubKey in colordef.genesis_scriptPubKeys:
            scriptPubKey_colordef_set = self.genesis_scriptPubKeys.setdefault(genesis_scriptPubKey, set())

            # Ensures the colordef doesn't have the same scriptPubKey multiple
            # times.
            assert colordef not in scriptPubKey_colordef_set
            scriptPubKey_colordef_set.add(colordef)

    def addcolorproof(self, colorproof):
        """Add a color proof to the database"""
        self.addcolordef(colorproof.colordef)

        if isinstance(colorproof, TransferredColorProof):
            # Add prevout proofs recursively first
            for prevout_proof in colorproof.prevout_proofs.values():
                self.addcolorproof(prevout_proof)

        self.colored_outpoints \
                .setdefault(colorproof.outpoint, {}) \
                .setdefault(colorproof.colordef, set()) \
                .add(colorproof)

    def addtx(self, tx):
        """Add a transaction to the database"""

        # FIXME: what should happen if you addtx() twice?

        colored_outpoints = {}

        txid = tx.GetHash()

        # Create genesis scriptPubKey proofs for the txouts
        for i, txout in enumerate(tx.vout):
            outpoint = COutPoint(txid, i)
            for colordef in self.genesis_scriptPubKeys.get(txout.scriptPubKey, set()):
                colorproof = GenesisScriptPubKeyColorProof(colordef, outpoint, tx)
                self.colored_outpoints \
                    .setdefault(outpoint, {}) \
                    .setdefault(colordef, set()) \
                    .add(colorproof)

        # Find colored inputs and sort the associated proofs by colordef
        prevout_proof_sets_by_colordef = {}
        for txin in tx.vin:
            for colordef, colorproofs in self.colored_outpoints.get(txin.prevout, {}).items():
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

                best_proof = next(iter(sorted(prevout_proof_set, key=proof_priority_key)))

                # Make sure that the color quantities proven by all proofs are
                # identical. (for now)
                assert all(prevout_proof.qty == best_proof.qty for prevout_proof in prevout_proof_set)

                prevout_proofs[outpoint] = best_proof

            # Now we can finally apply the kernel and start creating proofs for
            # the color movement for each colored output
            color_qty_by_outpoint = {outpoint:colorproof.qty for outpoint, colorproof in prevout_proofs.items()}
            for i, qty in enumerate(colordef.apply_kernel(tx, color_qty_by_outpoint)):

                if qty is None:
                    continue # Output isn't colored!

                outpoint = COutPoint(txid, i)
                colorproof = TransferredColorProof(colordef, outpoint, tx, prevout_proofs)
                assert colorproof.qty == qty
                self.colored_outpoints \
                    .setdefault(outpoint, {}) \
                    .setdefault(colordef, set()) \
                    .add(colorproof)


    def calc_state_hash(self):
        """Calculate a hash representing the state of the database"""

        def hash_dict(d, *, key_hash_func, value_hash_func):
            midstate = hashlib.sha256()
            # sorted() will return the dict items sorted by the has of each key
            for key_hash, value_hash in sorted((key_hash_func(key), value_hash_func(value)) for key, value in d.items()):
                midstate.update(key_hash)
                midstate.update(value_hash)
            return midstate.digest()

        def hash_set(objs, obj_hash_func=lambda obj: obj.hash):
            obj_hashes = [obj_hash_func(obj) for obj in objs]
            midstate = hashlib.sha256()
            for obj_hash in sorted(obj_hashes):
                midstate.update(obj_hash)
            return midstate.digest()

        midstate = hashlib.sha256()

        colordefs_digest = hash_set(self.colordefs)
        midstate.update(colordefs_digest)

        genesis_outpoints_digest = \
                hash_dict(self.genesis_outpoints,
                          key_hash_func=lambda outpoint: Hash(outpoint.serialize()),
                          value_hash_func=lambda colordef_set: hash_set(colordef_set))
        midstate.update(genesis_outpoints_digest)

        genesis_scriptPubKeys_digest = \
                hash_dict(self.genesis_scriptPubKeys,
                          key_hash_func=lambda scriptPubKey: Hash(scriptPubKey),
                          value_hash_func=lambda colordef_set: hash_set(colordef_set))
        midstate.update(genesis_scriptPubKeys_digest)

        def hash_colorproof_set_by_colordef_dict(d):
            return hash_dict(d, key_hash_func=lambda colordef: colordef.hash,
                                value_hash_func=lambda colorproof_set: hash_set(colorproof_set))

        colored_outpoints_digest = \
                hash_dict(self.colored_outpoints,
                          key_hash_func=lambda outpoint: Hash(outpoint.serialize()),
                          value_hash_func=lambda d: hash_colorproof_set_by_colordef_dict(d))
        midstate.update(colored_outpoints_digest)

        return midstate.digest()
