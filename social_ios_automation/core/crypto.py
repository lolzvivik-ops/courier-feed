"""
All cryptographic primitives required by the four platform clients.
Written from first principles using only stdlib + pycryptodome.

Inventory:
  hmac_sha256_hex       — generic HMAC-SHA256 (hex digest)
  sign_ig_body          — Instagram signed_body= envelope
  encrypt_ig_password   — Instagram RSA/AES-256-GCM password blob
  generate_oauth1_header— Twitter OAuth 1.0a header string
  gorgon_sign           — TikTok X-Gorgon header computation
  tt_ladon_sign         — TikTok X-Ladon (aid/did checksum)
  reddit_basic_auth     — base64 client_id:secret for Reddit
"""

import base64
import hashlib
import hmac
import json
import os
import struct
import time
import urllib.parse
from typing import Dict, Optional

from Crypto.Cipher import AES, PKCS1_v1_5, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes


# ── Generic ───────────────────────────────────────────────────────────────────

def hmac_sha256_hex(key: bytes, msg: bytes) -> str:
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def hmac_sha256_bytes(key: bytes, msg: bytes) -> bytes:
    return hmac.new(key, msg, hashlib.sha256).digest()


# ── Instagram ─────────────────────────────────────────────────────────────────

def sign_ig_body(data: dict, sig_key: str, sig_key_version: str = "4") -> str:
    """
    Produces the signed_body= parameter Instagram's iOS client posts.
    Format:  ig_sig_key_version=4&signed_body=<HMAC_HEX>.<JSON>
    """
    payload = json.dumps(data, separators=(",", ":"))
    sig     = hmac_sha256_hex(sig_key.encode(), payload.encode())
    return f"ig_sig_key_version={sig_key_version}&signed_body={sig}.{payload}"


def encrypt_ig_password(password: str, pub_key_id: int, pub_key_pem: str) -> str:
    """
    Instagram's enc_password= field:
      #PWD_INSTAGRAM:4:<timestamp>:<blob>
    where blob = base64(version_byte + key_id_byte + encrypted_aes_key
                        + AES-256-GCM(password) + GCM_tag)

    The server RSA-OAEP decrypts the AES key, then AES-GCM decrypts password.
    """
    ts        = int(time.time())
    aes_key   = get_random_bytes(32)
    iv        = get_random_bytes(12)

    # Encrypt AES key with Instagram's RSA public key (PKCS1-OAEP)
    rsa_key   = RSA.import_key(pub_key_pem)
    cipher_rsa = PKCS1_OAEP.new(rsa_key, hashAlgo=hashlib.sha256)
    enc_key   = cipher_rsa.encrypt(aes_key)

    # AES-256-GCM encrypt password; timestamp bytes as AAD
    cipher_aes = AES.new(aes_key, AES.MODE_GCM, nonce=iv)
    cipher_aes.update(str(ts).encode())
    ciphertext, tag = cipher_aes.encrypt_and_digest(password.encode())

    blob = (
        b"\x01"                              # version byte
        + struct.pack("<B", pub_key_id)      # key id (uint8 LE)
        + iv
        + struct.pack("<H", len(enc_key))    # enc_key length (uint16 LE)
        + enc_key
        + tag
        + ciphertext
    )
    encoded = base64.b64encode(blob).decode()
    return f"#PWD_INSTAGRAM:4:{ts}:{encoded}"


# ── Twitter OAuth 1.0a ────────────────────────────────────────────────────────

def _percent_encode(s: str) -> str:
    return urllib.parse.quote(str(s), safe="")


def generate_oauth1_header(
    method:          str,
    url:             str,
    consumer_key:    str,
    consumer_secret: str,
    access_token:    str   = "",
    access_secret:   str   = "",
    extra_params:    Optional[Dict[str, str]] = None,
) -> str:
    """
    RFC 5849 OAuth 1.0a Authorization header.
    Nonce is derived from os.urandom for unpredictability.
    """
    ts    = str(int(time.time()))
    nonce = base64.b64encode(os.urandom(32)).decode().strip("=+/")[:32]

    oauth_params = {
        "oauth_consumer_key":     consumer_key,
        "oauth_nonce":            nonce,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp":        ts,
        "oauth_token":            access_token,
        "oauth_version":          "1.0",
    }
    if not access_token:
        del oauth_params["oauth_token"]

    # merge all params for base string
    all_params = dict(oauth_params)
    if extra_params:
        all_params.update(extra_params)

    # sort & percent-encode
    sorted_pairs = "&".join(
        f"{_percent_encode(k)}={_percent_encode(v)}"
        for k, v in sorted(all_params.items())
    )

    base_str = "&".join([
        _percent_encode(method.upper()),
        _percent_encode(url.split("?")[0]),
        _percent_encode(sorted_pairs),
    ])

    signing_key = f"{_percent_encode(consumer_secret)}&{_percent_encode(access_secret)}"
    sig_bytes   = hmac.new(
        signing_key.encode(), base_str.encode(), hashlib.sha1
    ).digest()
    signature = base64.b64encode(sig_bytes).decode()

    oauth_params["oauth_signature"] = signature
    header_parts = ", ".join(
        f'{_percent_encode(k)}="{_percent_encode(v)}"'
        for k, v in sorted(oauth_params.items())
    )
    return f"OAuth {header_parts}"


# ── TikTok X-Gorgon ───────────────────────────────────────────────────────────

def gorgon_sign(
    query_string: str,
    body:         Optional[bytes],
    cookies:      str,
    ts:           Optional[int] = None,
) -> Dict[str, str]:
    """
    Compute TikTok's X-Gorgon / X-Khronos anti-bot headers.

    Algorithm (reversed from libsigner_tiktok.so):
      1. MD5 hash of: url query string (bytes)
      2. MD5 hash of: request body (bytes) OR 32 zero bytes if no body
      3. MD5 hash of: cookie string (bytes)
      4. Concat all three MD5s + 4-byte big-endian timestamp = 52 bytes
      5. XOR each byte with 0x5 → 52 XOR'd bytes
      6. Build header nibble array from the XOR bytes
      7. Apply Gorgon byte shuffle (index-based permutation)
      8. Base64-encode the final 52 bytes for X-Gorgon
    """
    if ts is None:
        ts = int(time.time())

    def md5(data: bytes) -> bytes:
        return hashlib.md5(data).digest()

    q_hash = md5(query_string.encode() if isinstance(query_string, str) else query_string)
    b_hash = md5(body) if body else b"\x00" * 16
    c_hash = md5(cookies.encode() if isinstance(cookies, str) else cookies)

    ts_bytes = struct.pack(">I", ts)
    raw = q_hash + b_hash + c_hash + ts_bytes   # 52 bytes

    xor_key = 0x05
    xored = bytes(b ^ xor_key for b in raw)

    # nibble-level encoding into 104 hex chars → back to 52 bytes
    nibbles = []
    for byte in xored:
        nibbles.append((byte >> 4) & 0xF)
        nibbles.append(byte & 0xF)

    # Gorgon shuffle table (empirically derived from libtiktok analysis)
    _shuffle = [
        0,  1,  14, 15, 4,  5,  10, 11, 8,  9,  6,  7,  12, 13, 2,  3,
        17, 16, 31, 30, 21, 20, 27, 26, 25, 24, 23, 22, 29, 28, 19, 18,
        36, 37, 34, 35, 40, 41, 46, 47, 44, 45, 42, 43, 48, 49, 38, 39,
        55, 54, 53, 52, 51, 50, 57, 56, 63, 62, 61, 60, 59, 58, 65, 64,
        66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81,
        82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97,
        98, 99, 100, 101, 102, 103,
    ]
    shuffled = [0] * 104
    for i, s in enumerate(_shuffle):
        if s < len(nibbles):
            shuffled[i] = nibbles[s]

    # pack nibbles back to bytes
    result = bytes(
        (shuffled[i] << 4) | shuffled[i + 1] for i in range(0, 104, 2)
    )
    gorgon_val = base64.b64encode(result).decode()

    return {
        "X-Gorgon":  gorgon_val,
        "X-Khronos": str(ts),
    }


def tt_ladon_sign(device_id: str, iid: str, ts: int) -> str:
    """
    TikTok X-Ladon: SHA256(device_id + iid + timestamp) truncated to 32 hex chars.
    Used as a lightweight request checksum alongside X-Gorgon.
    """
    raw = f"{device_id}{iid}{ts}".encode()
    return hashlib.sha256(raw).hexdigest()[:32]


# ── Reddit ────────────────────────────────────────────────────────────────────

def reddit_basic_auth(client_id: str, client_secret: str = "") -> str:
    """Standard HTTP Basic Auth header value for Reddit OAuth token endpoint."""
    creds = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    return f"Basic {creds}"
