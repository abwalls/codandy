"""Bounded, metadata-free drawing PNGs for explicit visual interpretation."""
import base64
import hashlib
import json
import struct
import zlib

from app.debugging.redaction import Redactor

PREFIX = "data:image/png;base64,"
MAX_BYTES = 2 * 1024 * 1024


def image_bytes(value):
    if not value.startswith(PREFIX) or len(value) > 2800000:
        raise ValueError("Use a PNG drawing preview no larger than 2 MiB")
    try:
        raw = base64.b64decode(value[len(PREFIX):], validate=True)
    except ValueError:
        raise ValueError("Invalid drawing image") from None
    if len(raw) > MAX_BYTES or raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Invalid drawing PNG")
    offset, parts, compressed = 8, [], bytearray()
    width = height = channels = 0
    ended = False
    while offset < len(raw):
        if offset + 12 > len(raw):
            raise ValueError("Truncated drawing PNG")
        size = struct.unpack(">I", raw[offset:offset + 4])[0]
        kind = raw[offset + 4:offset + 8]
        end = offset + size + 12
        if end > len(raw):
            raise ValueError("Truncated drawing PNG")
        data = raw[offset + 8:end - 4]
        if zlib.crc32(kind + data) != struct.unpack(">I", raw[end - 4:end])[0]:
            raise ValueError("Invalid drawing PNG checksum")
        if offset == 8 and kind != b"IHDR":
            raise ValueError("Missing drawing PNG header")
        if kind == b"IHDR":
            if offset != 8 or size != 13:
                raise ValueError("Invalid drawing PNG header")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", data)
            if not 1 <= width <= 2048 or not 1 <= height <= 2048 or depth != 8 or color not in (2, 6) or any((compression, filtering, interlace)):
                raise ValueError("Drawing PNG must be RGB/RGBA, noninterlaced and at most 2048 pixels per side")
            channels = 3 if color == 2 else 4
        elif kind == b"IDAT":
            compressed.extend(data)
        elif kind == b"IEND":
            if size or end != len(raw):
                raise ValueError("Invalid drawing PNG ending")
            ended = True
        elif kind[:1].isupper():
            raise ValueError("Unsupported drawing PNG chunk")
        # Drop ALL ancillary metadata, including embedded scene data and comments.
        if kind in (b"IHDR", b"IDAT", b"IEND"):
            parts.append(raw[offset:end])
        offset = end
    if not ended or not compressed:
        raise ValueError("Incomplete drawing PNG")
    expected = height * (width * channels + 1)
    try:
        decoder = zlib.decompressobj()
        pixels = decoder.decompress(bytes(compressed), expected + 1)
        if len(pixels) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ValueError("Invalid drawing PNG pixel data")
        if any(pixels[row * (width * channels + 1)] > 4 for row in range(height)):
            raise ValueError("Invalid drawing PNG filter")
    except zlib.error:
        raise ValueError("Invalid drawing PNG compression") from None
    return raw[:8] + b"".join(parts), width, height


def visual_scene(board, review):
    allowed = {e["id"] for e in review["packet"]["elements"]}
    keys = {"id", "type", "x", "y", "width", "height", "angle", "strokeColor", "backgroundColor",
            "fillStyle", "strokeWidth", "strokeStyle", "roughness", "opacity", "seed", "version",
            "versionNonce", "index", "roundness", "groupIds", "frameId", "boundElements", "containerId",
            "points", "pressures", "simulatePressure", "startBinding", "endBinding", "startArrowhead",
            "endArrowhead", "fontSize", "fontFamily", "textAlign", "verticalAlign", "lineHeight", "autoResize"}
    redactor = Redactor()
    result = []
    for element in board.scene.elements:
        if element["id"] not in allowed or element.get("isDeleted"):
            continue
        item = {k: v for k, v in element.items() if k in keys}
        for key in ("text", "originalText", "name"):
            if isinstance(element.get(key), str):
                item[key] = redactor.text(element[key], "drawing_preview")
        result.append(item)
    return result


def attach_image(review, value):
    raw, width, height = image_bytes(value)
    context = review["packet"]
    context["visual_input"] = {"sha256": hashlib.sha256(raw).hexdigest(), "width": width, "height": height,
                               "basis": "user-reviewed drawing; visual interpretations are hypotheses"}
    context["limitations"] = [v for v in context["limitations"] if "not interpreted visually" not in v]
    context["limitations"].append("Visual meanings and unbound arrow endpoints are uncertain; ask clarifying questions.")
    review["text"] = json.dumps(context, sort_keys=True, ensure_ascii=True)
    review["digest"] = hashlib.sha256(review["text"].encode()).hexdigest()
    review["image"] = PREFIX + base64.b64encode(raw).decode()
    review["image_info"] = context["visual_input"]
    return raw
