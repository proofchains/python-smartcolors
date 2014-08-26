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

import smartcolors.core

class AnnotatedColorDefHeader(smartcolors.core.ColorDefHeader):
    """Metadata bullshit goes here

    This stuff isn't consensus critical, so it's kept separate from the
    smartcolors.core module.
    """
    company_name = 'blah blah blah'
    url = 'https://scam.coin'
    ceo = 'Yo Dawg'
    age_of_ceo = 16
    astrological_sign = 'cancer'
