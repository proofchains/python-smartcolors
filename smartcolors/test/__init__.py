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

import json
import os

def test_data_path(name):
    return os.path.dirname(__file__) + '/data/' + name

def open_test_vector(name, mode='r'):
    return open(test_data_path(name), mode)

def load_test_vectors(name):
    with open_test_vector(name) as fd:
        for test_case in json.load(fd):
            if len(test_case) != 1:
                yield test_case

            else:
                # line comment
                pass
