"""Dependency-free COPY/literal development patch; never packages a full game."""
from __future__ import annotations
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path


def build_delta(original: bytes, patched: bytes) -> dict:
    anchors = {}
    for offset in range(0, len(original) - 31, 4096):
        anchors.setdefault(original[offset:offset + 32], offset)
    operations = []
    cursor = literal_start = 0
    while cursor + 32 <= len(patched):
        offset = anchors.get(patched[cursor:cursor + 32])
        if offset is None:
            cursor += 1
            continue
        length = 32
        while original[offset + length:offset + length + 4096] == patched[cursor + length:cursor + length + 4096] and offset + length + 4096 <= len(original) and cursor + length + 4096 <= len(patched):
            length += 4096
        while offset + length < len(original) and cursor + length < len(patched) and original[offset + length] == patched[cursor + length]:
            length += 1
        if cursor > literal_start:
            operations.append(["data", base64.b64encode(patched[literal_start:cursor]).decode("ascii")])
        operations.append(["copy", offset, length])
        cursor += length
        literal_start = cursor
    if literal_start < len(patched):
        operations.append(["data", base64.b64encode(patched[literal_start:]).decode("ascii")])
    return {"format": 1, "protocol": "enhanced_v1", "original_sha256": hashlib.sha256(original).hexdigest(),
            "patched_sha256": hashlib.sha256(patched).hexdigest(), "size": len(patched), "operations": operations}


def apply_delta(original: bytes, delta: dict) -> bytes:
    if delta.get("format") != 1 or hashlib.sha256(original).hexdigest() != delta.get("original_sha256"):
        raise ValueError("Patch does not match the original game")
    size = delta.get("size")
    if type(size) is not int or not 0 <= size <= 128 * 1024 * 1024:
        raise ValueError("Invalid patched size")
    chunks = []
    total = 0
    for operation in delta["operations"]:
        if len(operation) == 3 and operation[0] == "copy":
            _, start, length = operation
            if type(start) is not int or type(length) is not int or min(start, length) < 0 or start + length > len(original):
                raise ValueError("Invalid copy range")
            chunk = original[start:start + length]
        elif len(operation) == 2 and operation[0] == "data":
            try: chunk = base64.b64decode(operation[1], validate=True)
            except (ValueError, TypeError) as error: raise ValueError("Invalid literal") from error
        else:
            raise ValueError("Invalid patch operation")
        total += len(chunk)
        if total > size: raise ValueError("Patch exceeds expected size")
        chunks.append(chunk)
    result = b"".join(chunks)
    if len(result) != size or hashlib.sha256(result).hexdigest() != delta.get("patched_sha256"):
        raise ValueError("Patched game verification failed")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("patched", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    original, patched = args.original.read_bytes(), args.patched.read_bytes()
    delta = build_delta(original, patched)
    assert apply_delta(original, delta) == patched
    with args.output.open("xb") as stream:
        stream.write(gzip.compress(json.dumps(delta, separators=(",", ":")).encode(), mtime=0))
    print(f"Verified {len(delta['operations'])} operations; delta {args.output.stat().st_size:,} bytes")
