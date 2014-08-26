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

import bitcoin.core.serialize

class MerkleRadixTreeNode(bitcoin.core.serialize.ImmutableSerializable):
    """Merklized binary radix tree node"""
    __slots__ = ()

    KEYSIZE = 32

    PRUNED_NODE = 0
    INNER_NODE  = 1
    LEAF_NODE   = 2
    EMPTY_NODE  = 3

    PrunedNodeClass = None
    InnerNodeClass = None
    LeafNodeClass = None
    EmptyNodeClass = None

    @classmethod
    def from_items(cls, items=()):
        """Create a new merklized radix tree node from items

        items - (key, value) pairs
        depth - recursion depth to adjust keys by
        """
        # Convert all items to LeafNodes first.
        leaf_nodes = (cls.LeafNodeClass(k, v) for k,v in items)

        # Let the inner node class handle the rest. If there are zero or one
        # leaf nodes it'll return an EmptyNode, or just the leaf node, as
        # appropriate.
        return cls.InnerNodeClass.from_leaf_nodes(leaf_nodes)

    def get_hashed_data(self):
        """Return the data hashed to produce GetHash()"""
        raise NotImplementedError

    def CalcHash(self):
        return bitcoin.core.serialize.Hash(self.get_hashed_data())

    def _get(self, key, depth):
        """Actual implementation of __getitem__()"""
        raise NotImplementedError

    def __getitem__(self, key):
        """Return the value associated with key"""
        if len(key) != self.KEYSIZE:
            raise ValueError('Key must be exactly %d bytes' % self.KEYSIZE)
        return self._get(key, 0)

    def _set(self, leaf_node, depth):
        """Actual set() implementation goes here"""
        raise NotImplementedError

    def set(self, key, value):
        """Set key to value

        Returns a new node representing this part of the tree with that key
        appropriately set. The old tree not changed.
        """
        if len(key) != self.KEYSIZE:
            raise ValueError('Key must be exactly %d bytes' % self.KEYSIZE)
        leaf_node = self.LeafNodeClass(key, value)
        return self._set(leaf_node, 0)

    def pop(self, key):
        """Remove specified key

        Returns a new node representing this part of the tree with that key
        deleted. The old tree is not changed.
        """
        if len(key) != self.KEYSIZE:
            raise ValueError('Key must be exactly %d bytes' % self.KEYSIZE)
        return self._pop(key, 0)

class MerkleRadixTreePrunedNode(MerkleRadixTreeNode):
    __slots__ = ('pruned_hash', )
    def __init__(self, pruned_hash):
        object.__setattr__(self, 'pruned_hash', pruned_hash)

    def GetHash(self):
        return self.pruned_hash

MerkleRadixTreeNode.PrunedNodeClass = MerkleRadixTreePrunedNode

class MerkleRadixTreeEmptyNode(MerkleRadixTreeNode):
    instance = None

    def __new__(cls):
        if cls.instance is None:
            cls.instance = object.__new__(cls)

        return cls.instance

    def __init__(self):
        pass

    def get_hashed_data(self):
        return bytes([self.EMPTY_NODE])

    def _set(self, leaf_node, depth):
        # Empty nodes turn into leaf nodes when set
        return leaf_node

    def _get(self, key, depth):
        raise KeyError

    def _pop(self, key, depth):
        raise KeyError

MerkleRadixTreeNode.EmptyNodeClass = MerkleRadixTreeEmptyNode

class MerkleRadixTreeLeafNode(MerkleRadixTreeNode):
    __slots__ = ('key', 'value')

    def __init__(self, key, value):
        if len(key) != self.KEYSIZE:
            raise ValueError('Key must be exactly %d bytes' % self.KEYSIZE)

        object.__setattr__(self, 'key', key)
        object.__setattr__(self, 'value', value)

    def get_hashed_data(self):
        return self.value + self.key + bytes([self.LEAF_NODE])

    def _set(self, leaf_node, depth):
        if leaf_node.key == self.key:
            # Keys are identical, so the old leaf node is replaced by a new one
            return leaf_node

        else:
            return self.InnerNodeClass.from_leaf_nodes((self, leaf_node), depth)

    def _get(self, key, depth):
        if key != self.key:
            raise KeyError
        else:
            return self.value

    def _pop(self, key, depth):
        # Leaf nodes turn into empty nodes when deleted
        if key != self.key:
            raise KeyError
        else:
            return self.EmptyNodeClass()

MerkleRadixTreeNode.LeafNodeClass = MerkleRadixTreeLeafNode

class MerkleRadixTreeInnerNode(MerkleRadixTreeNode):
    __slots__ = ('left', 'right')

    def get_hashed_data(self):
        return self.left.GetHash() + self.right.GetHash() + bytes([self.INNER_NODE])

    def __new__(cls, left, right):
        # Ensure attempts to create deeper than necessary inner nodes fail.

        # Any combo of a EmptyNode and a (LeafNode, EmptyNode) can be replaced.
        # Note how this means you can only prune inner nodes, not leaf nodes.
        if isinstance(left, cls.EmptyNodeClass) and isinstance(right, (cls.EmptyNodeClass, cls.LeafNodeClass)):
            return right

        elif isinstance(right, cls.EmptyNodeClass) and isinstance(left, (cls.EmptyNodeClass, cls.LeafNodeClass)):
            return left

        self = super(MerkleRadixTreeInnerNode, cls).__new__(cls)
        object.__setattr__(self, 'left', left)
        object.__setattr__(self, 'right', right)
        return self

    @classmethod
    def from_leaf_nodes(cls, leaf_nodes, depth=0):
        left_leaves = []
        right_leaves = []

        prev_leaf = None
        for leaf_node in leaf_nodes:
            b = leaf_node.key[depth // 8] >> (7 - depth % 8) & 0b1

            # Detect duplicated keys
            if prev_leaf is not None and prev_leaf.key == leaf_node.key:
                raise KeyError('Duplicate key!')
            prev_leaf = leaf_node

            if b:
                left_leaves.append(leaf_node)

            else:
                right_leaves.append(leaf_node)

        if len(left_leaves) + len(right_leaves) == 0:
            # No leaves, return an EmptyNode instead.
            return cls.EmptyNodeClass()

        elif len(left_leaves) + len(right_leaves) == 1:
            # Just one leaf, so return it directly
            return (left_leaves + right_leaves)[0]

        else:
            left = cls.from_leaf_nodes(left_leaves, depth+1)
            right = cls.from_leaf_nodes(right_leaves, depth+1)
            return cls.InnerNodeClass(left, right)

    def _get(self, key, depth):
        b = key[depth // 8] >> (7 - depth % 8) & 0b1
        if b:
            return self.left._get(key, depth+1)
        else:
            return self.right._get(key, depth+1)

    def _set(self, leaf_node, depth):
        b = leaf_node.key[depth // 8] >> (7 - depth % 8) & 0b1

        new_left = self.left
        new_right = self.right

        if b:
            new_left = self.left._set(leaf_node, depth+1)

        else:
            new_right = self.right._set(leaf_node, depth+1)

        return self.InnerNodeClass(new_left, new_right)

    def _pop(self, key, depth):
        b = key[depth // 8] >> (7 - depth % 8) & 0b1

        new_left = self.left
        new_right = self.right

        if b:
            new_left = self.left._pop(key, depth+1)

        else:
            new_right = self.right._pop(key, depth+1)

        return self.InnerNodeClass(new_left, new_right)

MerkleRadixTreeNode.InnerNodeClass = MerkleRadixTreeInnerNode

class MerkleRadixTree:
    """Merklized binary radix tree

    This implementation prioritises simplicity and correctness over speed and
    genericity. It's designed to be used only with fixed sized keys produced by
    hash functions and the values stored are only stored at leaf nodes.
    """

    EMPTY_LEAF = b''

    def __init__(self, items=()):
        """Create a new tree

        items - (key, value) pairs to populate the new tree with
        """
        self.tip = MerkleRadixTreeNode(items)


    def GetHash(self):
        """Calculate the top hash of the tree"""
        return self.tip.GetHash()


class SHA256MerkleRadixTree:
    pass



class MerkleRadixTreeProof:
    pass
