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

import random
import unittest

from smartcolors.core.util import *

class Test_DagTuple(unittest.TestCase):
    def test_no_parents(self):
        dt = DagTuple()
        self.assertEqual(tuple(dt), ())

        dt = DagTuple((1,2,3))
        self.assertEqual(tuple(dt), (1,2,3))
        self.assertEqual(tuple(reversed(dt)), (3,2,1))

    def test_extend(self):
        dt1 = DagTuple((1,2))
        dt2 = dt1.extend((3,4))
        dt3 = dt2.extend((5,6))
        dt4 = dt3.extend((7,8))

        self.assertEqual(tuple(dt1), (1,2))
        self.assertEqual(tuple(dt2), (1,2,3,4))
        self.assertEqual(tuple(dt3), (1,2,3,4,5,6))
        self.assertEqual(tuple(dt4), (1,2,3,4,5,6,7,8))

    def test_null_extend(self):
        dt1 = DagTuple()
        dt2 = dt1.extend(())
        self.assertIs(dt1, dt2)

    def test_append(self):
        dt1 = DagTuple((1,))
        dt2 = dt1.append(2)
        dt3 = dt2.append(3)
        dt4 = dt3.append(4)

        self.assertEqual(tuple(dt1), (1,))
        self.assertEqual(tuple(dt2), (1,2,))
        self.assertEqual(tuple(dt3), (1,2,3,))
        self.assertEqual(tuple(dt4), (1,2,3,4,))

    def test_merge_no_common_parents(self):
        dt_a = DagTuple(['a'])
        dt_b = DagTuple(['b'])

        dt_ab = dt_a.merge([dt_b])
        self.assertEqual(tuple(dt_ab), ('a','b'))

        dt_ba = dt_b.merge([dt_a])
        self.assertEqual(tuple(dt_ba), ('b','a'))

        dt_c = DagTuple(['b'])

    def test_immutable(self):
        dt = DagTuple()
        with self.assertRaises(AttributeError):
            dt.foo = 'bar'
        with self.assertRaises(AttributeError):
            dt.parents = (DagTuple(),)
        with self.assertRaises(AttributeError):
            dt.values = (1,2,3)
