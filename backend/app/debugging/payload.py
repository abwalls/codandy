"""Bounded decoding for imported or fetched debugging payloads."""

import json
import re
import zlib

from app.debugging.models import DebuggingLimits


class NormalizationError(ValueError):
    """A safe, user-presentable rejection of an unsupported or unsafe payload."""


_STRING = re.compile(r'"(?:[^"\\]|\\.)*+"', re.DOTALL)
_BRACKET = re.compile(r"[\[\]{}]")


def read_bounded(data: bytes, limits: DebuggingLimits) -> bytes:
    if len(data) > limits.max_payload_bytes:
        raise NormalizationError("Payload exceeds the byte budget")
    if data[:2] != b"\x1f\x8b":
        return data
    # The budget applies to the expanded bytes: a small archive can inflate far beyond it.
    inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        expanded = inflater.decompress(data, limits.max_payload_bytes + 1)
    except zlib.error as exc:
        raise NormalizationError("Compressed payload is invalid") from exc
    if len(expanded) > limits.max_payload_bytes or inflater.unconsumed_tail:
        raise NormalizationError("Payload exceeds the byte budget after decompression")
    if not inflater.eof or inflater.unused_data:
        raise NormalizationError("Compressed payload is incomplete or has trailing data")
    return expanded


def json_depth(text: str) -> int:
    """Nesting depth measured before parsing, so deep input never reaches the JSON parser."""
    depth = deepest = 0
    for match in _BRACKET.finditer(_STRING.sub('""', text)):
        if match.group() in "[{":
            depth += 1
            deepest = max(deepest, depth)
        else:
            depth -= 1
    return deepest


def _reject_constant(name: str):
    raise ValueError(f"Unsupported JSON constant {name}")


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def load_json(data: bytes, limits: DebuggingLimits):
    raw = read_bounded(data, limits)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise NormalizationError("Payload is not UTF-8 JSON") from exc
    if json_depth(text) > limits.max_json_depth:
        raise NormalizationError(f"Payload exceeds JSON nesting depth {limits.max_json_depth}")
    try:
        return json.loads(text, parse_constant=_reject_constant, object_pairs_hook=_unique_keys)
    except (ValueError, RecursionError) as exc:
        raise NormalizationError("Payload is not valid JSON") from exc
