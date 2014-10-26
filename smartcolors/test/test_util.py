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

    def test_iter_no_common_parents(self):
        dt_a = DagTuple(['a'])
        dt_b = DagTuple(['b'])
        dt_c = DagTuple(['c'])

        dt_ab = DagTuple(parents=[dt_a, dt_b])
        self.assertEqual(tuple(dt_ab), ('a','b'))

        dt_ba = DagTuple(parents=[dt_b, dt_a])
        self.assertEqual(tuple(dt_ba), ('b','a'))

        dt_abc = DagTuple(parents=[dt_a, dt_b, dt_c])
        self.assertEqual(tuple(dt_abc), ('a','b','c'))

    def test_iter(self):
        dt1a = DagTuple(['1a'])
        dt2a = dt1a.append('2a')
        dt2b = dt1a.append('2b')

        dt3a = DagTuple(['3a'], parents=[dt2a, dt2b])
        self.assertEqual(tuple(dt3a), ('1a', '2a', '2b', '3a'))

        dt3b = DagTuple(['3b'], parents=[dt2b, dt2a])
        self.assertEqual(tuple(dt3b), ('1a', '2b', '2a', '3b'))

        dt4 = DagTuple(['4'], parents=[dt3a, dt3b])
        self.assertEqual(tuple(dt4), ('1a', '2a', '2b', '3a', '3b', '4'))

        dt1b = DagTuple(['1b'])
        dt5 = DagTuple(['5'], parents=[dt4, dt1b])
        self.assertEqual(tuple(dt5), ('1a', '2a', '2b', '3a', '3b', '4', '1b', '5'))

    def test_very_deep_graph(self):
        dt = DagTuple()

        for v in range(10000):
            dt = dt.append(v)

        self.assertEqual(tuple(dt), tuple(range(10000)))

    def test_immutable(self):
        dt = DagTuple()
        with self.assertRaises(AttributeError):
            dt.foo = 'bar'
        with self.assertRaises(AttributeError):
            dt.parents = (DagTuple(),)
        with self.assertRaises(AttributeError):
            dt.values = (1,2,3)
