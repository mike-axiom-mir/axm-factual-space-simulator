# AXM drand quicknet verifier

This is a narrow optional integrity module, not part of AXM's simulation root.

It pins `@noble/curves` 1.6.0 and `@noble/hashes` 1.5.0 and implements the same quicknet checks used by the official drand JavaScript client:

1. the requested round is preserved;
2. `randomness == SHA-256(signature)`;
3. the unchained message is `SHA-256(uint64_be(round))`;
4. the 48-byte G1 signature verifies against the pinned 96-byte G2 quicknet public key with the RFC 9380 G1 DST.

Run `install.sh` on Linux/macOS or `install.bat` on Windows. AXM refuses to consume a drand packet as entropy when this cryptographic verifier is unavailable or returns false.
