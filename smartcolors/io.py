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

import logging

import bitcoin.core
import proofmarshal.memoize
import smartcolors.core

class FileSerializer:
    """Memoized proofmarshal file format

    Adds some minor niceties like magic bytes at the start and a checksum at
    the end, as well as memoization via the MemoizedStreamContexts
    """

    MAGIC = None
    OBJ_CLASS = None

    @classmethod
    def stream_serialize(cls, obj, fd):
        assert len(cls.MAGIC) == 32
        fd.write(cls.MAGIC)
        fd.write(b'\x00') # version byte, zero for now; can decide this later...

        ctx = proofmarshal.memoize.MemoizedStreamSerializationContext(fd)
        ctx.write_obj(None, obj)

        assert len(obj.hash) == 32
        fd.write(obj.hash)

    @classmethod
    def stream_deserialize(cls, fd, check_hash=True):
        assert len(cls.MAGIC) == 32
        actual_magic = fd.read(len(cls.MAGIC))
        assert cls.MAGIC == actual_magic # FIXME: raise an exception here...

        version = fd.read(1)
        assert version == b'\x00'

        ctx = proofmarshal.memoize.MemoizedStreamDeserializationContext(fd)
        obj = ctx.read_obj(None, cls.OBJ_CLASS)

        expected_hash = fd.read(32)
        if obj.hash != expected_hash:
            # FIXME: probably better ways to do this...
            msg = 'deserialized obj hash != expected hash: %s != %s' % \
                        (bitcoin.core.b2x(obj.hash), bitcoin.core.b2x(expected_hash))

            if check_hash:
                raise Exception(msg)
            else:
                logging.warning(msg)

        return obj

class ColorDefFileSerializer(FileSerializer):
    MAGIC = (b'\x00Smartcolors\x00\xfc\xbe\x88' +
             b'\x00Colordef\x00\xa8\xed\xdd\xf2\x14\x01')

    OBJ_CLASS = smartcolors.core.ColorDef

class ColorProofFileSerializer(FileSerializer):
    MAGIC = (b'\x00Smartcolors\x00\xf8\xac\xdc' +
             b'\x00Colorproof\x00\xcb\x93\xf2\xc5')

    OBJ_CLASS = smartcolors.core.ColorProof
