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

import hashlib
import io

"""Cryptographic proof marshalling

Provides serialization and deserialization for complex, immutable,
cryptographic proofs.
"""

class SerializationContext:
    """Context for serialization

    Allows multiple serialization targets to share the same codebase, for
    instance bytes, memoized serialization, hashing, JSON, etc.
    """

    def write_varuint(self, attr_name, value):
        """Write a variable-length unsigned integer"""
        raise NotImplementedError

class DeserializationContext:
    """Context for deserialization

    Allows multiple deserialization sources to share the same codebase, for
    instance bytes, memoized serialization, hashing, JSON, etc.
    """

    def read_varuint(self, attr_name, value):
        """Write a variable-length unsigned integer"""
        raise NotImplementedError


class StreamSerializationContext(SerializationContext):
    def __init__(self, fd):
        self.fd = io.BytesIO()

    def write_varuint(self, attr_name, value):
        # unsigned little-endian base128 format (LEB128)
        if value == 0:
            self.fd.write(b'\x00')

        else:
            while value != 0:
                b = value & 0b01111111
                if value > 0b01111111:
                    b |= 0b10000000
                self.fd.write(bytes([b]))
                if value <= 0b01111111:
                    break
                value >>= 7

class StreamDeserializationContext(DeserializationContext):
    def __init__(self, fd):
        self.fd = fd

    def fd_read(self, l):
        r = self.fd.read(l)
        assert len(r) == l # FIXME: raise exception
        return r

    def read_varuint(self, attr_name):
        value = 0
        shift = 0

        while True:
            b = self.fd_read(1)[0]
            value |= (b & 0b01111111) << shift
            if not (b & 0b10000000):
                break
            shift += 7

        return value

class BytesSerializationContext(StreamSerializationContext):
    def __init__(self):
        super().__init__(io.BytesIO())

    def getbytes(self):
        """Return the bytes serialized to date"""
        return self.fd.getvalue()

class BytesDeserializationContext(StreamDeserializationContext):
    def __init__(self, buf):
        super().__init__(io.BytesIO(buf))

    # FIXME: need to check that there isn't extra crap at end of object


class JsonSerializationContext:
    """serialize to a human-readable JSON-compatible dict"""

    def __init__(self):
        self.pairs = {}

    def write_varuint(self, attr_name, value):
        assert attr_name not in self.pairs
        self.pairs[attr_name] = value

class JsonDeserializationContext:
    """deserialize a human-readable JSON-compatible attribute-value pairs"""

    def __init__(self, pairs=None):
        self.pairs = pairs

    def read_varuint(self, attr_name):
        return self.pairs[attr_name]

class HashSerializationContext:
    """Serialization context for calculating hashes of objects

    Serialization is never recursive in this context; when encountering an
    object its hash is used instead.
    """

class ImmutableProof:
    """Base class for immutable proof objects


    """
    __slots__ = []

    def __setattr__(self, name, value):
        raise AttributeError('Object is immutable')

    def __delattr__(self, name):
        raise AttributeError('Object is immutable')

    def ctx_serialize(self, ctx):
        pass

    def ctx_deserialize(self, ctx):
        pass

    def serialize(self):
        """Serialize to bytes"""
        ctx = BytesSerializationContext()
        self.ctx_serialize(ctx)
        return ctx.getbytes()

    @classmethod
    def deserialize(cls, buf):
        """Deserialize from bytes"""
        ctx = BytesDeserializationContext(buf)
        self = cls.__new__(cls)
        self.ctx_deserialize(ctx)
        return self

    def json_serialize(self):
        """Serialize to JSON-compatible attribute-value pairs"""
        ctx = JsonSerializationContext()
        self.ctx_serialize(ctx)
        return ctx.pairs

    @classmethod
    def json_deserialize(cls, pairs):
        """Serialize from JSON-compatible attribute-value pairs"""
        ctx = JsonDeserializationContext(pairs)
        self = cls.__new__(cls)
        self.ctx_deserialize(ctx)
        return self
