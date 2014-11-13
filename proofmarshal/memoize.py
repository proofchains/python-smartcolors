# Copyright (C) 2014 Peter Todd <pete@petertodd.org>
#
# This file is part of python-proofmarshal.
#
# It is subject to the license terms in the LICENSE file found in the top-level
# directory of this distribution.
#
# No part of python-proofmarshal, including this file, may be copied, modified,
# propagated, or distributed except according to the terms contained in the
# LICENSE file.

import binascii

import proofmarshal

class MemoizedStreamSerializationContext(proofmarshal.StreamSerializationContext):
    """Memoized serialization to a stream"""
    def __init__(self, fd):
        super().__init__(fd)

        self.serialized_objs = {}

    def write_obj(self, attr_name, obj, serialization_class=None):
        obj_hash = None
        if serialization_class is None:
            obj_hash = obj.hash
            serialization_class = obj.__class__

        else:
            obj_hash = serialization_class.calc_hash(obj)

        if obj_hash in self.serialized_objs:
            idx = self.serialized_objs[obj_hash]
            assert idx > 0
            self.write_varuint(None, idx)

        else:
            self.write_varuint(None, 0)

            super().write_obj(attr_name, obj, serialization_class=serialization_class)

            idx = len(self.serialized_objs)+1
            self.serialized_objs[obj_hash] = idx

class MemoizedStreamDeserializationContext(proofmarshal.StreamDeserializationContext):
    """Memoized deserialization of a stream"""
    def __init__(self, fd):
        super().__init__(fd)
        self.deserialized_objs = []

    def read_obj(self, attr_name, deserialization_class):
        idx = self.read_varuint(None)
        if idx:
            obj = self.deserialized_objs[idx-1]
            return obj

        else:
            obj = super().read_obj(attr_name, deserialization_class)
            self.deserialized_objs.append(obj)
            idx = len(self.deserialized_objs)
            return obj
