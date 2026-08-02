import { Buffer } from 'node:buffer';
import process from 'node:process';
import { bls12_381 as bls } from '@noble/curves/bls12-381';
import { sha256 } from '@noble/hashes/sha2';

const QUICKNET_SCHEME = 'bls-unchained-g1-rfc9380';
const QUICKNET_DST = 'BLS_SIG_BLS12381G1_XMD:SHA-256_SSWU_RO_NUL_';

function hex(bytes) {
  return Buffer.from(bytes).toString('hex');
}

function roundBuffer(round) {
  const buffer = Buffer.alloc(8);
  buffer.writeBigUInt64BE(BigInt(round));
  return buffer;
}

function verifySignatureOnG1(signatureHex, message, publicKeyHex, dst) {
  const publicKey = bls.G2.ProjectivePoint.fromHex(publicKeyHex);
  const hashedMessage = bls.G1.hashToCurve(message, { DST: dst });
  const generator = bls.G2.ProjectivePoint.BASE;
  const signature = bls.G1.ProjectivePoint.fromHex(signatureHex);
  const left = bls.pairing(hashedMessage, publicKey.negate(), true);
  const right = bls.pairing(signature, generator, true);
  const product = bls.fields.Fp12.mul(right, left);
  return bls.fields.Fp12.eql(product, bls.fields.Fp12.ONE);
}

async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  return Buffer.concat(chunks).toString('utf8');
}

try {
  const packet = JSON.parse(await readStdin());
  if (packet.scheme_id !== QUICKNET_SCHEME) throw new Error('unsupported drand scheme');
  if (packet.dst !== QUICKNET_DST) throw new Error('unexpected quicknet DST');
  const round = Number(packet.round);
  if (!Number.isSafeInteger(round) || round < 1) throw new Error('invalid round');
  const signatureBytes = Buffer.from(packet.signature, 'hex');
  const randomnessHashValid = hex(sha256(signatureBytes)) === packet.randomness;
  const message = sha256(roundBuffer(round));
  const blsSignatureValid = verifySignatureOnG1(
    packet.signature,
    message,
    packet.public_key,
    QUICKNET_DST,
  );
  const valid = randomnessHashValid && blsSignatureValid;
  process.stdout.write(JSON.stringify({
    valid,
    randomness_hash_valid: randomnessHashValid,
    bls_signature_valid: blsSignatureValid,
    message_rule: 'SHA-256(uint64_be(round))',
    pairing_rule: 'e(H(message), -public_key) * e(signature, G2_generator) == 1',
    dst: QUICKNET_DST,
  }));
  process.exitCode = valid ? 0 : 1;
} catch (error) {
  process.stdout.write(JSON.stringify({ valid: false, error: String(error?.message || error) }));
  process.exitCode = 2;
}
