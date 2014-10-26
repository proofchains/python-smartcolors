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

class DagTuple:
    """Tuple-like stored as a DAG"""

    __slots__ = ['parents', 'values']

    def __setattr__(self, name, value):
        raise AttributeError('DagTuple instances are immutable')

    def __delattr__(self, name):
        raise AttributeError('DagTuple instances are immutable')

    def __init__(self, iterable=(), *, parents=()):
        object.__setattr__(self, 'parents', tuple(parents))
        object.__setattr__(self, 'values', tuple(iterable))

    def extend(self, iterable):
        """Extend by appending elements from the iterable

        Returns a new instance unless the iterable is empty, in which case self
        is returned.
        """
        r = self.__class__(iterable, parents=(self,))
        if r.values:
            return r
        else:
            return self

    def append(self, value):
        """Append a new element

        Returns a new instance. Equivalent to self.extend((value,))
        """
        return self.extend((value,))

    def __iter__(self):
        """Iterate in depth-first order"""

        visited = set()
        stack = [(iter(self.parents), self.values)]

        while stack:
            try:
                parent = next(stack[-1][0])

                if id(parent) not in visited:
                    visited.add(id(parent))
                    stack.append((iter(parent.parents), parent.values))

            except StopIteration:
                yield from stack[-1][1]
                stack.pop()
