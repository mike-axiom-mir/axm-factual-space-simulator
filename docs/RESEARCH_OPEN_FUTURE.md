# Research note — unresolved futures and auditable randomness

## Python local entropy

Python documents `secrets` as the module for cryptographically strong random values and distinguishes it from the ordinary `random` module, which is intended for modelling and simulation rather than security-sensitive unpredictability.

AXM uses `secrets.token_hex(32)` only at declared event-resolution points. The token is then preserved in the event receipt so a completed event can be reproduced.

Source: https://docs.python.org/3/library/secrets.html

## Public randomness beacons

NIST's randomness-beacon reference describes periodic public pulses containing fresh random bits together with timestamps, signatures, metadata and hash-chain support. These properties are useful when an event should be auditable by parties who do not trust one local host.

Source: https://csrc.nist.gov/pubs/ir/8213/ipd

The NIST site also warns that public beacon values must not be used as secret cryptographic keys. AXM uses them only as public event-resolution material.

## Distributed beacons

drand generates public randomness in rounds using threshold BLS signatures. Its documentation describes the random value as a hash of the reconstructed threshold signature, allowing the output to be publicly checked against network information.

Sources:

- https://docs.drand.love/docs/cryptography/
- https://docs.drand.love/docs/specification/

AXM v0.2 can fetch and preserve a drand Quicknet packet. Full BLS verification is deliberately left as a later module rather than falsely claimed complete.

## Party contributions

Commit-before-reveal protocols are the classic route for two or more remote parties to contribute to an outcome without revealing their choice early enough for another participant to adapt theirs.

Foundational publication record:

- https://research.ibm.com/publications/coin-flipping-by-telephone

AXM's starter uses SHA-256 commitments. It verifies changed reveals but does not prevent strategic non-reveal/abort behaviour.

## Design conclusion

A single RNG mode cannot solve every problem:

- deterministic streams protect reproducibility;
- local entropy protects the future from the original seed;
- public beacons improve third-party auditability;
- commit–reveal reduces single-seat control;
- hash-chained ledgers preserve what happened afterward.

AXM therefore exposes the authority choice instead of hiding it.
