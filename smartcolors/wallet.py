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

import bitcoin.core

from smartcolors.core import ColorProof, add_msbdrop_value_padding

def create_nSequence_color_tx(prevouts, amounts_out, get_change_scriptPubKey,
                              calc_dust_limit=lambda scriptPubKey: 0,
                              use_steg=True,
                              COutPoint=bitcoin.core.COutPoint,
                              CTxIn=bitcoin.core.CTxIn,
                              CTxOut=bitcoin.core.CTxOut):
    """Create a transaction to move color around via nSequence/MSB-drop

    prevouts    - iterable of ColorProofs/COutPoints corresponding to the desired inputs of the
                  transaction, in order
    amounts_out - iterable of (qty, scriptPubKey, nValue) corresponding to the
                  desired outputs of the transaction. Uncolored outputs are
                  marked with qty set to None; colored have nValue is None.

    Only one color is supported; all prevouts proofs must use the same
    colordef. If (colored) change is left over get_change_scriptPubKey() will
    be called with the difference and is expected to return either a
    scriptPubKey or None.

    Returns (vin, vout)
    """
    amounts_out = list(amounts_out)

    prevout_proofs = tuple(prevout for prevout in prevouts if isinstance(prevout, ColorProof))
    if not all(prevproof.colordef == prevout_proofs[0].colordef for prevproof in prevout_proofs):
        raise Exception('Mismatched prevout proof colordefs; all colors must be the same')

    qty_in = sum(prevproof.qty for prevproof in prevout_proofs)
    qty_out = sum(qty if qty else 0 for qty, scriptPubKey, nValue in amounts_out)

    if qty_out > qty_in:
        raise Exception('Color qty out > qty in: %d > %d' % (qty_out, qty_in))

    # done prior to actually calling get_change_scriptPubKey so we don't create
    # change addresses unnecessarily
    if len(amounts_out) > (16 if qty_in == qty_out else 15):
        raise Exception('Too many outputs to represent with nSequence')

    if qty_in > qty_out:
        change_qty = qty_in - qty_out
        change_scriptPubKey = get_change_scriptPubKey(change_qty)
        if change_scriptPubKey is not None:
            amounts_out.append((change_qty, change_scriptPubKey, None))

    colored_txout_mask = 0
    vout = []
    for i, (qty, scriptPubKey, nValue) in enumerate(amounts_out):
        if qty is not None:
            assert nValue is None

            nValue = add_msbdrop_value_padding(qty, calc_dust_limit(scriptPubKey))
            colored_txout_mask |= 1 << i

        else:
            assert nValue is not None

        vout.append(CTxOut(nValue, scriptPubKey))

    # Create inputs
    vin = []
    for prevout in prevouts:
        nSequence = 0xFFFFFFFF
        if isinstance(prevout, ColorProof):
            colorproof = prevout
            prevout = colorproof.outpoint

            nSequence = colored_txout_mask << 16
            if use_steg:
                nSequence ^= colorproof.colordef.nSequence_pad(prevout)

            nSequence = (nSequence & 0xFFFFFF00) | 0x7E | (1 << 7 if use_steg else 0)

        vin.append(CTxIn(prevout, nSequence=nSequence))

    return (vin, vout)
