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
import random
import unittest

from bitcoin.core.serialize import Hash

from smartcolors.core.merkleradixtree import *

class Test_MerkleRadixTreeNode(unittest.TestCase):
    def test_creation(self):
        H = Hash

        def p(buf):
            return buf.ljust(32, b'\x00')

        # An empty leaf node
        empty_leaf = MerkleRadixTreeNode.from_items()
        self.assertEqual(empty_leaf.GetHash(), H(b'\x03'))

        # Leaf node
        leaf_node = MerkleRadixTreeNode.from_items([(p(b'\x00'), b'\xff')])


        # Node with two leaves
        tip = MerkleRadixTreeNode.from_items([(p(b'\x80'), b'\xaa'),
                                              (p(b'\x00'), b'\xbb')])

        self.assertEqual(tip.left.key, p(b'\x80'))
        self.assertEqual(tip.left.value, b'\xaa')

        self.assertEqual(tip.right.key, p(b'\x00'))
        self.assertEqual(tip.right.value, b'\xbb')

        self.assertEqual(tip.GetHash(),
                         H(tip.left.GetHash() + tip.right.GetHash() + b'\x01'))


        # As above, but this time the first bit collides, so both values end up
        # on the left side.
        tip = MerkleRadixTreeNode.from_items([(p(b'\xc0'), b'\xaa'),
                                              (p(b'\x80'), b'\xbb')])

        self.assertEqual(tip.left.left.key, p(b'\xc0'))
        self.assertEqual(tip.left.left.value, b'\xaa')

        self.assertEqual(tip.left.right.key, p(b'\x80'))
        self.assertEqual(tip.left.right.value, b'\xbb')

        self.assertEqual(tip.left.GetHash(),
                         H(tip.left.left.GetHash() + tip.left.right.GetHash() + b'\x01'))

        self.assertTrue(tip.right is MerkleRadixTreeEmptyNode())


        # Eight level deep collision
        tip = MerkleRadixTreeNode.from_items([(p(b'\xff\x80'), b'\xaa'),
                                              (p(b'\xff\x00'), b'\xbb')])

        self.assertEqual(tip.left.left.left.left.left.left.left.left.left.value, b'\xaa')
        self.assertEqual(tip.left.left.left.left.left.left.left.left.right.value, b'\xbb')

        # Subtrees should be identical, even if the main tree isn't
        tip2 = MerkleRadixTreeNode.from_items([(p(b'\xff\x80'), b'\xaa'),
                                               (p(b'\xff\x00'), b'\xbb'),
                                               (p(b'\x00\x00'), b'\xcc')])

        self.assertEqual(tip.left.GetHash(), tip2.left.GetHash())

    def test_empty_keys(self):
        # Empty keys fail
        with self.assertRaises(ValueError):
            MerkleRadixTreeNode.from_items([(b'a', b'hello world')])

    def test_key_collision(self):
        with self.assertRaises(KeyError):
            MerkleRadixTreeNode.from_items([(b'a'*32, b'a'),
                                            (b'a'*32, b'b')])

    def test_getitem(self):
        def p(buf):
            return buf.ljust(32, b'\x00')

        tip = MerkleRadixTreeEmptyNode()
        with self.assertRaises(KeyError):
            tip[p(b'\x00')]

        # Tree with a single leaf node
        tip = MerkleRadixTreeNode.from_items([(p(b'\x00'), b'\xaa')])

        self.assertEqual(tip[p(b'\x00')], b'\xaa')

        with self.assertRaises(KeyError):
            tip[p(b'\xff')]

        # One inner node, with left and right being leaves
        tip = MerkleRadixTreeNode.from_items([(p(b'\x00'), b'\xaa'),
                                              (p(b'\xff'), b'\xbb')])

        self.assertEqual(tip[p(b'\x00')], b'\xaa')
        self.assertEqual(tip[p(b'\xff')], b'\xbb')

        with self.assertRaises(KeyError):
            tip[p(b'\xaa')]

        # First bit collides
        tip = MerkleRadixTreeNode.from_items([(p(b'\x80'), b'\xaa'),
                                              (p(b'\xff'), b'\xbb')])

        self.assertEqual(tip[p(b'\x80')], b'\xaa')
        self.assertEqual(tip[p(b'\xff')], b'\xbb')

        # fails at tip.left.left in the leaf node
        with self.assertRaises(KeyError):
            tip[p(b'\xff\x01')]

        # fails at tip.right in the empty node
        with self.assertRaises(KeyError):
            tip[p(b'\x00')]

    def test_set(self):
        def p(buf):
            return buf.ljust(32, b'\x00')

        def T(actual_tree, expected_tree_items):
            expected_tree = MerkleRadixTreeNode.from_items(expected_tree_items)
            self.assertEqual(actual_tree.GetHash(), expected_tree.GetHash())

        tip = MerkleRadixTreeNode.from_items()

        # Empty node should be converted to leaf node
        tip2 = tip.set(p(b'\x00'), b'a')

        T(tip2, [(p(b'\x00'), b'a')])

        # Leaf should be converted into inner with two leaves
        tip3 = tip2.set(p(b'\xff'), b'b')
        T(tip3, [(p(b'\x00'), b'a'),
                 (p(b'\xff'), b'b')])

        # Adding another leaf, single-bit collision on tip.right
        tip4 = tip3.set(p(b'\x40'), b'c')
        T(tip4, [(p(b'\x00'), b'a'),
                 (p(b'\xff'), b'b'),
                 (p(b'\x40'), b'c')])

        # 4-bit collision starting at tip.left
        tip5 = tip4.set(p(b'\xf0'), b'd')
        T(tip5, [(p(b'\x00'), b'a'),
                 (p(b'\xff'), b'b'),
                 (p(b'\x40'), b'c'),
                 (p(b'\xf0'), b'd')])

        # 7-bit on tip.right
        tip6 = tip5.set(p(b'\x41'), b'e')
        T(tip6, [(p(b'\x00'), b'a'),
                 (p(b'\xff'), b'b'),
                 (p(b'\x40'), b'c'),
                 (p(b'\xf0'), b'd'),
                 (p(b'\x41'), b'e')])

        # Collide part-way down tip.right
        tip7 = tip6.set(p(b'\x48'), b'f')
        T(tip7, [(p(b'\x00'), b'a'),
                 (p(b'\xff'), b'b'),
                 (p(b'\x40'), b'c'),
                 (p(b'\xf0'), b'd'),
                 (p(b'\x41'), b'e'),
                 (p(b'\x48'), b'f')])

        # Sub-parts of the tree should be reused between different versions
        self.assertIs(tip7.right.left.right.right.right,
                      tip6.right.left.right.right.right)

        self.assertIs(tip7.left,  tip6.left)
        self.assertIs(tip6.left,  tip5.left)
        self.assertIs(tip5.right, tip4.right)
        self.assertIs(tip4.left,  tip3.left)
        self.assertIs(tip3.right, tip2)

    def test_del(self):
        def p(buf):
            return buf.ljust(32, b'\x00')

        def T(actual_tree, expected_tree_items):
            expected_tree = MerkleRadixTreeNode.from_items(expected_tree_items)
            self.assertEqual(actual_tree.GetHash(), expected_tree.GetHash())

        # Anything from an empty tree raises an error of course.
        tip = MerkleRadixTreeNode.from_items()
        with self.assertRaises(KeyError):
            tip.pop(p(b'\x00'))

        # Deleting from a leaf with a non-existent key
        tip = MerkleRadixTreeNode.from_items([(p(b'\x00'), b'a')])
        with self.assertRaises(KeyError):
            tip.pop(p(b'\xff'))

        # Deleting a leaf with the correct key results in an empty node
        tip = MerkleRadixTreeNode.from_items([(p(b'\x00'), b'a')])
        tip2 = tip.pop(p(b'\x00'))
        self.assertIs(tip2, MerkleRadixTreeNode.EmptyNodeClass())

        # An inner with two leaves is converted into a leaf when one of the
        # leaves is deleted.
        tip = MerkleRadixTreeNode.from_items([(p(b'\x00'), b'a'),
                                              (p(b'\xff'), b'b')])
        tip2 = tip.pop(p(b'\xff'))
        T(tip2, [(p(b'\x00'), b'a')])

        # As above, but this time the first bit collided
        tip = MerkleRadixTreeNode.from_items([(p(b'\x80'), b'a'),
                                              (p(b'\xff'), b'b')])
        self.assertIsInstance(tip, MerkleRadixTreeNode.InnerNodeClass)
        self.assertIsInstance(tip.right, MerkleRadixTreeNode.EmptyNodeClass)
        tip2 = tip.pop(p(b'\xff'))

        # Everything collapses down to a single leaf node
        T(tip2, [(p(b'\x80'), b'a')])
        self.assertIsInstance(tip2, MerkleRadixTreeNode.LeafNodeClass)

        # Three key example, this time it can't collapse down.
        tip = MerkleRadixTreeNode.from_items([(p(b'\x80'), b'a'),
                                              (p(b'\xff'), b'b'),
                                              (p(b'\x00'), b'c')])
        self.assertIsInstance(tip, MerkleRadixTreeNode.InnerNodeClass)
        self.assertIsInstance(tip.right, MerkleRadixTreeNode.LeafNodeClass)
        self.assertIsInstance(tip.left, MerkleRadixTreeNode.InnerNodeClass)
        tip2 = tip.pop(p(b'\xff'))
        T(tip2, [(p(b'\x80'), b'a'),
                 (p(b'\x00'), b'c')])

        # Eight bit deep collision
        tip = MerkleRadixTreeNode.from_items([(p(b'\x00\x00'), b'a'),
                                              (p(b'\x00\xff'), b'b')])
        tip2 = tip.pop(p(b'\x00\x00'))
        T(tip2, [(p(b'\x00\xff'), b'b')])

        # Three key example, right side deleted
        tip = MerkleRadixTreeNode.from_items([(p(b'\x80'), b'a'),
                                              (p(b'\xff'), b'b'),
                                              (p(b'\x00'), b'c')])
        tip2 = tip.pop(p(b'\x00'))
        T(tip2, [(p(b'\x80'), b'a'),
                 (p(b'\xff'), b'b')])

        # Four key example
        tip = MerkleRadixTreeNode.from_items([(p(b'\x80'), b'a'),
                                              (p(b'\xff'), b'b'),
                                              (p(b'\x00'), b'c'),
                                              (p(b'\x01'), b'd')])
        tip2 = tip.pop(p(b'\x00'))
        T(tip2, [(p(b'\x80'), b'a'),
                 (p(b'\xff'), b'b'),
                 (p(b'\x01'), b'd')])

    def test_random_sets_deletes(self):
        expected_contents = set()

        tip = MerkleRadixTreeNode.from_items()

        def grow(grow_prob, n):
            nonlocal tip
            for i in range(n):
                if random.random() < grow_prob:
                    new_item = (os.urandom(32), os.urandom(32))
                    expected_contents.add(new_item)
                    tip = tip.set(new_item[0], new_item[1])

                elif len(expected_contents) > 0:
                    del_item = expected_contents.pop()
                    tip = tip.pop(del_item[0])

        def modify(n):
            nonlocal tip
            for i in range(n):
                k,old_value = expected_contents.pop()
                new_value = os.urandom(32)
                expected_contents.add((k, new_value))
                tip = tip.set(k, new_value)

        def check():
            expected_tip = MerkleRadixTreeNode.from_items([(k,v) for k,v in expected_contents])
            self.assertEqual(tip.GetHash(), expected_tip.GetHash())

            # test all keys for existence
            for k,v in expected_contents:
                self.assertEqual(tip[k], v)

            # test some keys for non-existence
            for i in range(1000):
                non_key = os.urandom(32)
                with self.assertRaises(KeyError):
                    tip[non_key]

        n = 1000
        grow(1.0, n)
        check()

        grow(0.5, n)
        check()

        modify(n)
        check()

        # delete everything and check that we end up with an empty node
        for k,v in expected_contents:
            tip = tip.pop(k)

        self.assertIs(tip, MerkleRadixTreeNode.EmptyNodeClass())
