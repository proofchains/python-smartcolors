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
import tempfile

from bitcoin.core import b2x, b2lx, lx, x
import bitcoin.core
import bitcoin.core.script

import smartcolors.core.db
import smartcolors.io

class PersistentSet:
    """File-backed set"""

    def __init__(self, *, root_dir_path):
        self.root_dir_path = os.path.abspath(root_dir_path)


    def _get_elem_filename(self, elem):
        raise NotImplementedError

    def _serialize_elem(self, elem):
        raise NotImplementedError

    def _deserialize_elem(self, fd):
        raise NotImplementedError


    def add(self, elem):
        # No effect if element is already present
        if elem in self:
            return

        elem_filename = self._get_elem_filename(elem)

        os.makedirs(self.root_dir_path, exist_ok=True)

        # Write the element to disk as a new temporary file in the directory
        with tempfile.NamedTemporaryFile(dir=self.root_dir_path, prefix=elem_filename + '-tmp-') as fd:
            self._serialize_elem(elem, fd)

            fd.flush()

            # Hardlink the file to it's correct name, which atomically makes it
            # available to readers. The temporary name will be unlinked for us
            # by NamedTemporaryFile.
            try:
                os.link(fd.name, os.path.join(self.root_dir_path, elem_filename))
            except FileExistsError as exp:
                # FIXME: actually handle this!
                raise exp


    def __iter__(self):
        try:
            elem_filenames = os.listdir(self.root_dir_path)
        except FileNotFoundError as exp:
            return

        for elem_filename in elem_filenames:
            with open(os.path.join(self.root_dir_path, elem_filename), 'rb') as fd:
                yield self._deserialize_elem(fd)

    def __contains__(self, elem):
        elem_filename = self._get_elem_filename(elem)
        return os.path.exists(os.path.join(self.root_dir_path, elem_filename))

class PersistentDict:
    """File-backed set"""

    def __init__(self, *, root_dir_path):
        self.root_dir_path = os.path.abspath(root_dir_path)


    def _key_to_filename(self, key):
        raise NotImplementedError

    def _filename_to_key(self, filename):
        raise NotImplementedError

    def _get_item(self, key_abspath):
        raise NotImplementedError


    def _key_to_abspath(self, key):
        return os.path.join(self.root_dir_path, self._key_to_filename(key))

    def __contains__(self, key):
        return os.path.exists(self._key_to_abspath(key))

    def __getitem__(self, key):
        key_abspath = self._key_to_abspath(key)
        if not os.path.exists(key_abspath):
            raise KeyError(key)
        else:
            return self._get_item(key_abspath)

    def get(self, key, default_value=None):
        try:
            return self[key]
        except KeyError:
            return default_value

    def __setitem__(self, key, value):
        raise NotImplementedError

    def setdefault(self, key, default_value=None):
        try:
            return self[key]
        except KeyError:
            pass

        return default_value

    def __iter__(self):
        try:
            key_filenames = os.listdir(self.root_dir_path)
        except FileNotFoundError as exp:
            return

        for key_filename in key_filenames:
            yield self._filename_to_key(key_filename)

    def keys(self):
        yield from self.__iter__()

    def values(self):
        yield from [self[key] for key in self.keys()]

    def items(self):
        for key in self:
            yield (key, self[key])


class PersistentColorDefSet(PersistentSet):
    def _get_elem_filename(self, colordef):
        return b2x(colordef.hash) + '.scdef'

    def _serialize_elem(self, colordef, fd):
        smartcolors.io.ColorDefFileSerializer.stream_serialize(colordef, fd)

    def _deserialize_elem(self, fd):
        return smartcolors.io.ColorDefFileSerializer.stream_deserialize(fd)

class PersistentColorProofSet(PersistentSet):
    def _get_elem_filename(self, colorproof):
        return b2x(colorproof.hash) + '.scproof'

    def _serialize_elem(self, colorproof, fd):
        smartcolors.io.ColorProofFileSerializer.stream_serialize(colorproof, fd)

    def _deserialize_elem(self, fd):
        return smartcolors.io.ColorProofFileSerializer.stream_deserialize(fd)

class PersistentGenesisOutPointsDict(PersistentDict):
    def _key_to_filename(self, outpoint):
        return '%s:%d' % (b2lx(outpoint.hash), outpoint.n)

    def _filename_to_key(self, filename):
        hex_hash, str_n = filename.split(':')
        return bitcoin.core.COutPoint(lx(hex_hash), int(str_n))

    def _get_item(self, key_abspath):
        return PersistentColorDefSet(root_dir_path=key_abspath)

    def setdefault(self, key, default_value=None):
        assert default_value == set()

        default_value = PersistentColorDefSet(root_dir_path=self._key_to_abspath(key))
        return super().setdefault(key, default_value=default_value)

class PersistentGenesisScriptPubKeysDict(PersistentDict):
    def _key_to_filename(self, scriptPubKey):
        if scriptPubKey:
            return b2x(scriptPubKey)
        else:
            # gotta handle the empty case!
            return '_'

    def _filename_to_key(self, filename):
        if filename == '_':
            return bitcoin.core.script.CScript()
        else:
            return bitcoin.core.script.CScript(x(filename))

    def _get_item(self, key_abspath):
        return PersistentColorDefSet(root_dir_path=key_abspath)

    def setdefault(self, key, default_value=None):
        assert default_value == set()

        default_value = PersistentColorDefSet(root_dir_path=self._key_to_abspath(key))
        return super().setdefault(key, default_value=default_value)

class PersistentColorProofsByColorDefDict(PersistentDict):
    def _key_to_filename(self, colordef):
        return b2x(colordef.hash)

    def _filename_to_key(self, filename):
        # Bit of a hack to say the least...
        colordef_filename = os.path.join(self.root_dir_path, '..', '..', 'colordefs', filename + '.scdef')
        with open(colordef_filename, 'rb') as fd:
            return smartcolors.io.ColorDefFileSerializer.stream_deserialize(fd)

    def _get_item(self, key_abspath):
        return PersistentColorProofSet(root_dir_path=key_abspath)

    def setdefault(self, key, default_value=None):
        assert default_value == set()

        default_value = PersistentColorProofSet(root_dir_path=self._key_to_abspath(key))
        return super().setdefault(key, default_value=default_value)

class PersistentColoredOutPointsDict(PersistentDict):
    def _key_to_filename(self, outpoint):
        return '%s:%d' % (b2lx(outpoint.hash), outpoint.n)

    def _filename_to_key(self, filename):
        hex_hash, str_n = filename.split(':')
        return bitcoin.core.COutPoint(lx(hex_hash), int(str_n))

    def _get_item(self, key_abspath):
        return PersistentColorProofsByColorDefDict(root_dir_path=key_abspath)

    def setdefault(self, key, default_value=None):
        assert default_value == {}

        default_value = PersistentColorProofsByColorDefDict(root_dir_path=self._key_to_abspath(key))
        return super().setdefault(key, default_value=default_value)

class PersistentColorProofDb(smartcolors.core.db.ColorProofDb):
    def __init__(self, root_dir_path):
        self.root_dir_path = os.path.abspath(root_dir_path)
        self.colordefs = PersistentColorDefSet(root_dir_path=os.path.join(self.root_dir_path, 'colordefs'))
        self.genesis_outpoints = PersistentGenesisOutPointsDict(root_dir_path=os.path.join(self.root_dir_path, 'genesis_outpoints'))
        self.genesis_scriptPubKeys = PersistentGenesisScriptPubKeysDict(root_dir_path=os.path.join(self.root_dir_path, 'genesis_scriptPubKeys'))
        self.colored_outpoints = PersistentColoredOutPointsDict(root_dir_path=os.path.join(self.root_dir_path, 'colored_outpoints'))
