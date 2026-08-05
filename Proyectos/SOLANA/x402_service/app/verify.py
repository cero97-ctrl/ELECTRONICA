"""Verificación de firma Ed25519 (nacl) + utilidades base58.

La dirección pública de Solana ES la clave pública Ed25519 (codificada en
base58). El cliente firma el mensaje canónico de paywall.py con su keypair y
envía la firma en X-Solana-Signature (base58, formato estándar de Solana).
"""
from __future__ import annotations

import base64
import binascii

import nacl.exceptions
import nacl.signing

# Alfabeto base58 de Bitcoin (usado por Solana).
_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58MAP = {c: i for i, c in enumerate(_ALPHABET)}


class Base58Error(ValueError):
    pass


def b58decode(s: str) -> bytes:
    """Decodifica base58 a bytes."""
    if not s:
        raise Base58Error("cadena base58 vacía")
    n = 0
    for ch in s:
        try:
            n = n * 58 + _B58MAP[ch]
        except KeyError:
            raise Base58Error(f"carácter no válido en base58: {ch!r}")
    nbytes = bytearray()
    while n:
        nbytes.append(n & 0xFF)
        n >>= 8
    pad = len(s) - len(s.lstrip("1"))
    return b"\x00" * pad + bytes(reversed(nbytes))


def b58encode(data: bytes) -> str:
    """Codifica bytes a base58."""
    n = int.from_bytes(data, "big")
    out = []
    while n:
        n, r = divmod(n, 58)
        out.append(_ALPHABET[r])
    pad = len(data) - len(data.lstrip(b"\x00"))
    return "1" * pad + "".join(reversed(out))


def _decode_sig(value: str) -> bytes:
    """Acepta firma en base58 (Solana) o hex, la devuelve como 64 bytes."""
    try:
        raw = b58decode(value)
        if len(raw) == 64:
            return raw
    except Base58Error:
        pass
    try:
        raw = bytes.fromhex(value)
        if len(raw) == 64:
            return raw
    except ValueError:
        pass
    raise ValueError("X-Solana-Signature debe ser base58 o hex de 64 bytes")


def verify_signature(
    from_address: str, message: str, signature_b58_or_hex: str
) -> None:
    """Verifica que la firma corresponde a from_address sobre message.

    Lanza nacl.exceptions.BadSignatureError si no es válida.
    """
    pubkey = b58decode(from_address)
    if len(pubkey) != 32:
        raise ValueError(f"X-Solana-From no parece una dirección válida: {from_address}")
    sig = _decode_sig(signature_b58_or_hex)
    vk = nacl.signing.VerifyKey(pubkey)
    vk.verify(message.encode("utf-8"), sig)
