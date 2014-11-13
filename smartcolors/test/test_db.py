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
            actual_genesis_outpoints['%s:%d' % (b2lx(outpoint.hash), outpoint.n)] = \
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
            json_outpoint = '%s:%d' % (b2lx(outpoint.hash), outpoint.n)
            actual_color_qtys_by_colordef = actual_outpoints.setdefault(json_outpoint, {})

            for colordef, colorproofs in color_qtys_by_colordef.items():
                colorproofs = tuple(colorproofs)
                if len(colorproofs) != 1:
                    import pdb; pdb.set_trace()
                colorproof = colorproofs[0]
                actual_color_qtys_by_colordef[b2x(colordef.hash)] = colorproof.qty

        self.assertDictEqual(expected_outpoints, actual_outpoints,
                msg='%s: assert_outpoint_qtys(): mismatch' % test_name)

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
