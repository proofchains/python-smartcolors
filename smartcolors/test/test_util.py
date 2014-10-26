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
        n = 10000
        v1a = ['1a_%d' % i for i in range(n)]
        v1b = ['1b_%d' % i for i in range(n)]
        v2a = ['2a_%d' % i for i in range(n)]
        v2b = ['2b_%d' % i for i in range(n)]

        def repeated_append(dt, values):
            for value in values:
                dt = dt.append(value)
            return dt

        dt1a = repeated_append(DagTuple(), v1a)
        dt1b = repeated_append(DagTuple(), v1b)

        self.assertEqual(list(dt1a), v1a)
        self.assertEqual(list(dt1b), v1b)

        dt1ab = DagTuple(['1ab'], parents=(dt1a, dt1b))
        self.assertEqual(list(dt1ab), v1a + v1b + ['1ab'])

        dt2a = repeated_append(dt1ab, v2a)
        dt2b = repeated_append(dt1ab, v2b)
        self.assertEqual(list(dt2a), v1a + v1b + ['1ab'] + v2a)
        self.assertEqual(list(dt2b), v1a + v1b + ['1ab'] + v2b)

        dt2ab = DagTuple(['2ab'], parents=(dt2a, dt2b))
        self.assertEqual(list(dt2ab), v1a + v1b + ['1ab'] + v2a + v2b + ['2ab'])

    def test_immutable(self):
        dt = DagTuple()
        with self.assertRaises(AttributeError):
            dt.foo = 'bar'
        with self.assertRaises(AttributeError):
            dt.parents = (DagTuple(),)
        with self.assertRaises(AttributeError):
            dt.values = (1,2,3)
