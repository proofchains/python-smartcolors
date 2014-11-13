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

"""sctool command line arguments"""


parser_define = subparsers.add_parser('definecolor',
    help='Create a color definition file')
parser_define.add_argument('-x', metavar=('TXID:N', 'QTY'),
    action='append', type=str, nargs=2,
    default=[],
    dest='genesis_outpoints',
    help='Transaction outpoint')
parser_define.add_argument('-a', metavar='ADDR',
    action='append', type=str,
    default=[],
    dest='genesis_addrs',
    help='Address')
parser_define.add_argument('-s', metavar='SCRIPTPUBKEY',
    action='append', type=str,
    default=[],
    dest='genesis_scriptPubKeys',
    help='Hex-encoded scriptPubKey')
parser_define.add_argument('--stegkey', metavar='HEX',
    type=str,
    default=None,
    dest='stegkey',
    help='Stegkey')
parser_define.add_argument('--birthdate', metavar='BLOCKHEIGHT',
    type=int,
    default=0,
    dest='birthdate_blockheight',
    help='Birthdate blockheight')
parser_define.add_argument('fd', type=argparse.FileType('xb'), metavar='FILE',
    help='Color definition file')
parser_define.set_defaults(cmd_func=cmd_definecolor)

parser_decodecolordef = subparsers.add_parser('decodecolordef',
    help='Decode a color definition file')
parser_decodecolordef.add_argument('fd', type=argparse.FileType('rb'), metavar='FILE',
    help='Color definition file')
parser_decodecolordef.set_defaults(cmd_func=cmd_decodecolordef)

parser_define = subparsers.add_parser('definecolor',
    help='Create a color definition file')
parser_define.add_argument('-x', metavar=('TXID:N', 'QTY'),
    action='append', type=str, nargs=2,
    default=[],
    dest='genesis_outpoints',
    help='Transaction outpoint')
parser_define.add_argument('-a', metavar='ADDR',
    action='append', type=str,
    default=[],
    dest='genesis_addrs',
    help='Address')
parser_define.add_argument('-s', metavar='SCRIPTPUBKEY',
    action='append', type=str,
    default=[],
    dest='genesis_scriptPubKeys',
    help='Hex-encoded scriptPubKey')
parser_define.add_argument('--stegkey', metavar='HEX',
    type=str,
    default=None,
    dest='stegkey',
    help='Stegkey')
parser_define.add_argument('--birthdate', metavar='BLOCKHEIGHT',
    type=int,
    default=0,
    dest='birthdate_blockheight',
    help='Birthdate blockheight')
parser_define.add_argument('fd', type=argparse.FileType('xb'), metavar='FILE',
    help='Color definition file')
parser_define.set_defaults(cmd_func=cmd_definecolor)

parser_decodecolordef = subparsers.add_parser('decodecolordef',
    help='Decode a color definition file')
parser_decodecolordef.add_argument('fd', type=argparse.FileType('rb'), metavar='FILE',
    help='Color definition file')
parser_decodecolordef.set_defaults(cmd_func=cmd_decodecolordef)
