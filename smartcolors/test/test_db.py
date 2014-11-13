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
from smartcolors.core.db import *

from smartcolors.test import test_data_path, load_test_vectors

def run_proof_test(self, test_name):
    colordb = ColorProofDb()

    def parse_str_outpoint(str_outpoint):
        """Parse txid:n into a COutPoint"""
        assert str_outpoint.count(':') == 1
        hex_txid, str_n = str_outpoint.split(':')
        return COutPoint(lx(hex_txid), int(str_n))

    def str_outpoint(outpoint):
        """Turn COutPoint into txid:n formatted string"""
        return '%s:%d' % (b2lx(outpoint.hash), outpoint.n)

    actions = {}
    def define_action(func):
        actions[func.__name__] = func
        return func

    @define_action
    def load_colordef(hex_colordef, hex_hash):
        serialized_colordef = x(hex_colordef)
        colordef = ColorDef.deserialize(serialized_colordef)

        self.assertEqual(b2x(colordef.hash), hex_hash,
                msg='%s: load_colordef(): colordef hashes mismatched' % test_name)

        colordb.addcolordef(colordef)

    @define_action
    def assert_genesis_outpoints(expected_genesis_outpoints):
        actual_genesis_outpoints = {}
        for outpoint, colordef_set in colordb.genesis_outpoints.items():
            actual_genesis_outpoints[str_outpoint(outpoint)] = \
                    list(sorted(b2x(colordef.hash) for colordef in colordef_set))

        self.assertDictEqual(expected_genesis_outpoints, actual_genesis_outpoints,
                msg='%s: assert_genesis_outpoints(): mismatch' % test_name)

    @define_action
    def assert_genesis_scriptPubKeys(expected_genesis_scriptPubKeys):
        actual_genesis_scriptPubKeys = {}
        for scriptPubKey, colordef_set in colordb.genesis_scriptPubKeys.items():
            actual_genesis_scriptPubKeys['%s' % b2x(scriptPubKey)] = \
                    list(sorted(b2x(colordef.hash) for colordef in colordef_set))

        self.assertDictEqual(expected_genesis_scriptPubKeys, actual_genesis_scriptPubKeys,
                msg='%s: assert_genesis_scriptPubKeys(): mismatch' % test_name)

    @define_action
    def assert_outpoint_qtys(expected_outpoints):
        actual_outpoints = {}
        for outpoint, color_qtys_by_colordef in colordb.colored_outpoints.items():
            actual_color_qtys_by_colordef = actual_outpoints.setdefault(str_outpoint(outpoint), {})

            for colordef, colorproofs in color_qtys_by_colordef.items():
                colorproofs = tuple(colorproofs)
                if len(colorproofs) != 1:
                    import pdb; pdb.set_trace()
                colorproof = colorproofs[0]
                actual_color_qtys_by_colordef[b2x(colordef.hash)] = colorproof.qty

        self.assertDictEqual(expected_outpoints, actual_outpoints,
                msg='%s: assert_outpoint_qtys(): mismatch' % test_name)

    @define_action
    def assert_outpoint_proofs(str_outpoint, expected_proof_hashes):
        """Assert a specific outpoint has the specified proof(s)"""
        outpoint = parse_str_outpoint(str_outpoint)

        actual_colorproofs = set()
        for colordef, colorproof_set in colordb.colored_outpoints[outpoint].items():
            # check for proofs in more than one colordef
            assert not actual_colorproofs.intersection(colorproof_set)
            actual_colorproofs.update(colorproof_set)

        actual_proof_hashes = set(b2x(colorproof.hash) for colorproof in actual_colorproofs)
        expected_proof_hashes = set(expected_proof_hashes)

        self.assertSetEqual(actual_proof_hashes, expected_proof_hashes,
                msg='%s: assert_proofs(): mismatch' % test_name)

    @define_action
    def assert_state_hash(expected_state_hash):
        """Assert a hash of the entire ColorProofDb state"""
        actual_state_hash = colordb.calc_state_hash()
        self.assertEqual(expected_state_hash, b2x(actual_state_hash),
                msg='%s: assert_state_hash(): mismatch' % test_name)

    @define_action
    def debug_outpoint_proofs(str_outpoint):
        """Drop into a debugger"""
        outpoint = parse_str_outpoint(str_outpoint)
        proofs_by_colordef = colordb.colored_outpoints[outpoint]
        all_proofs = set()
        for colorproofs_set in proofs_by_colordef.values():
            all_proofs.update(colorproofs_set)

        # for when there's just one
        proof = tuple(all_proofs)[0]

        print('\n')
        print(proofs_by_colordef)
        print('\n')

        import pdb
        import json
        pdb.set_trace()


    @define_action
    def addtx(hex_tx):
        tx = CTransaction.deserialize(x(hex_tx))
        colordb.addtx(tx)

    for action, *args in load_test_vectors(test_name):
        if action not in actions:
            self.fail('%s: Unknown action %s' % (test_name, action))

        actions[action](*args)

class Test_ColorProofDb(unittest.TestCase):
    def test(self):
        """Data-driven tests"""
        for proof_test in sorted(os.listdir(test_data_path('colorproofdb/'))):
            if proof_test[0] == '.':
                continue
            run_proof_test(self, 'colorproofdb/' + proof_test)
