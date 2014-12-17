python-smartcolors
==================

Requirements
============

python-bitcoinlib v0.3.0


ELI5 Overview
=============

This library implements a colored coin kernel, an efficient way for issuers to
define their colored coins, and finally, an efficient way to prove that
specific transaction outputs are colored according to those definitions.


The Kernel
----------

The movement of color from an input to an output is specified with the
nSequence field. This 32-bit field is present in each transaction input and is
signed by the signature for that transaction input. Each bit set to 1 means
whatever color is present on that input is assigned to that corresponding
output; if more than one output is assigned for a given input the color from
the input is distributed among all those outputs.


Color Definitions
-----------------

A smartcolors color definition is similar to a Bitcoin block: a set of genesis
points are hashed into a special type of merkle tree called a "merbinner tree",
and that hash is included in a header. A genesis point simply means that a
particular transaction output is defined to be colored by the issuer. Because
the definition is a tree you can prune the definition to securely prove that
some subset of the points was part of the definition - kinda like how SPV
wallets verify transactions by verifying a pruned block with only some
transactions actually in it.


Color Proofs
------------

With a pruned color definition and a set of transactions we can now prove that
a specific set of transaction outputs are colored. This allows color tracking
servers to give their clients proofs, which means those clients don't need to
trust those servers as the tracking servers can't lie to them. All the client
needs to do is run the Smartcolors kernel on each transaction in the proof,
just like the tracking server does. The proof is small and verifying it is
quick because only a subset of all transactions for that particular color need
to be verified to check if the outputs in their wallet are in fact colored.


Handling the Dust Limit
-----------------------

Bitcoin Core won't relay or mine transactions that have transaction outputs
with less than 546 satoshis. Since colored coins represents units of an asset
with satoshis we need to get around this dust limit in a simple way.
Smartcolors uses Most Significant Bit Drop (MSB-Drop) encoding to work around
this problem. The most significant bit set to 1 of the transaction output value
is simply dropped, and the remaining value interpreted as the color quantity.
Secondly the least significant bit turns this feature on and off.


Unit Tests
==========

python3 -m unittest discover -s proofmarshal
python3 -m unittest discover -s smartcolors
