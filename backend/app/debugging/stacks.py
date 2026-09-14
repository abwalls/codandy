"""Pasted stack traces: Python tracebacks, JavaScript (V8/Firefox) stacks and .NET exceptions.

Runtimes print frames in different orders. Python prints the most recent call last, while
V8, Firefox and .NET print it first. Every parser normalizes to oldest caller first and
states its reading. Unrecognized lines are counted, never guessed into frames.
"""

import re

from app.debugging.builder import ObservationBuilder, RawException, RawFrame
from app.debugging.models import DebuggingLimits, Observation, ObservationSource
from app.debugging.payload import NormalizationError

MAX_LINE_CHARS = 4096

_HEADER = re.compile(
    r"^(?:Uncaught )?(?P<type>[A-Za-z_$][\w$.`+]*)(?: \[[^\]]{1,80}\])?(?::\s?(?P<value>.*))?$", re.DOTALL)

_PY_TRACEBACK = "Traceback (most recent call last):"
_PY_CHAIN = {
    "The above exception was the direct cause of the following exception:": "direct_cause",
    "During handling of the above exception, another exception occurred:": "during_handling",
}
_PY_FRAME = re.compile(r'^\s+File "(?P<path>[^"]+)", line (?P<line>\d+)(?:, in (?P<function>.+?))?\s*$')
_PY_REPEAT = re.compile(r"^\s*\[Previous line repeated (?P<count>\d+) more times?\]\s*$")
_PY_MARKER = re.compile(r"^[\s^~]+$")

_JS_LOCATION_END = re.compile(r":\d+:\d+\)?\s*$")
_V8_FRAME = re.compile(
    r"^\s*at (?:(?P<async>async) )?(?:(?P<function>[^()]*?) \((?P<location>.+)\)|(?P<bare>\S.*?))\s*$")
_FIREFOX_FRAME = re.compile(r"^(?P<function>[^@\s]*)@(?P<location>\S.*?)\s*$")
_LOCATION = re.compile(r"^(?P<path>.+?):(?P<line>\d+)(?::(?P<column>\d+))?$")
_NODE_OMITTED = re.compile(r"^\s*\.\.\. (?P<count>\d+) lines? matching cause stack trace \.\.\.\s*$")

_DOTNET_FRAME = re.compile(
    r"^\s*at (?P<method>[^\s(]+)\((?P<args>[^)]*)\)(?: in (?P<path>.+):line (?P<line>\d+))?\s*$")
_DOTNET_INNER_END = re.compile(r"^\s*--- End of inner exception stack trace ---\s*$")
_DOTNET_ASYNC = re.compile(
    r"^\s*--- End of stack trace from previous location(?: where exception was thrown)? ---\s*$")
_DOTNET_ARROW = re.compile(r"\s*--->\s*")

UNSUPPORTED = ("Unrecognized stack format. Supported pasted formats are Python tracebacks, "
               "JavaScript (V8 or Firefox) stacks and .NET exception text.")


def _header(text: str) -> tuple[str | None, str | None]:
    text = text.strip()
    match = _HEADER.match(text)
    if not match:
        return None, text or None
    return match["type"], match["value"]


def detect_format(lines: list[str]) -> str:
    if any(line.strip() == _PY_TRACEBACK for line in lines):
        return "python_traceback"
    javascript = sum(1 for line in lines if _JS_LOCATION_END.search(line)
                     and (_V8_FRAME.match(line) or _FIREFOX_FRAME.match(line)))
    dotnet = sum(1 for line in lines
                 if _DOTNET_FRAME.match(line) and not _JS_LOCATION_END.search(line))
    if not javascript and not dotnet:
        raise NormalizationError(UNSUPPORTED)
    return "javascript_stack" if javascript >= dotnet else "dotnet_stack"


def _python(lines: list[str], builder: ObservationBuilder) -> tuple[list[RawException], list[str]]:
    if any("Exception Group Traceback" in line for line in lines):
        raise NormalizationError(
            "Python exception group tracebacks are not supported yet; paste one member traceback")
    sections: list[tuple[list[str], str | None]] = []
    body: list[str] = []
    for line in lines:
        if relation := _PY_CHAIN.get(line.strip()):
            sections.append((body, relation))
            body = []
        else:
            body.append(line)
    sections.append((body, None))
    exceptions, unrecognized = [], 0
    for body, relation in sections:
        start = next((i for i, line in enumerate(body) if line.strip() == _PY_TRACEBACK), None)
        if start is not None:
            unrecognized += sum(1 for line in body[:start] if line.strip())
            body = body[start + 1:]
        frames: list[RawFrame] = []
        omitted, tail = 0, []
        for line in body:
            if tail:
                tail.append(line)
            elif match := _PY_FRAME.match(line):
                frames.append(RawFrame(provider_index=len(frames), path=match["path"],
                                       line=int(match["line"]), function=match["function"]))
            elif repeat := _PY_REPEAT.match(line):
                omitted += int(repeat["count"])
            elif frames and line.startswith(" ") and line.strip():
                # The printed source line; caret/tilde position markers are not evidence.
                if not _PY_MARKER.match(line) and not frames[-1].context:
                    frames[-1].context.append((frames[-1].line, line.strip()))
            elif line.strip():
                tail.append(line)
        while tail and not tail[-1].strip():
            tail.pop()
        if not frames and not tail:
            continue
        kind, value = _header(tail[0]) if tail else (None, None)
        if len(tail) > 1:
            value = "\n".join(part for part in [value or "", *tail[1:]]).strip("\n") or None
        exceptions.append(RawException(type=kind, value=value, frames=frames,
                                       frames_omitted=omitted, relation_to_next=relation))
    if unrecognized:
        builder.limitations.append(
            f"{unrecognized} line(s) before a traceback header were not interpreted")
    return exceptions, [
        "Python prints the most recent call last; printed frame order was kept.",
        ("Chained exceptions print oldest first; the 'direct cause' and 'during handling' "
        "sentences set each record's relation to the next."),
    ]


def _js_frame(position: int, function: str | None, location: str) -> RawFrame:
    location = location.strip()
    match = _LOCATION.match(location)
    if not match:
        return RawFrame(provider_index=position, function=function or None, path=location or None)
    return RawFrame(provider_index=position, function=function or None, path=match["path"],
                    line=int(match["line"]),
                    column=int(match["column"]) if match["column"] else None)


def _javascript(lines: list[str],
                builder: ObservationBuilder) -> tuple[list[RawException], list[str]]:
    printed: list[tuple[RawFrame, bool]] = []
    header: list[str] = []
    omitted = unrecognized = 0
    ended = False
    for line in lines:
        if ended:
            unrecognized += bool(line.strip())
            continue
        v8 = _V8_FRAME.match(line)
        firefox = None if v8 else _FIREFOX_FRAME.match(line)
        if v8 and (printed or v8["location"] or _JS_LOCATION_END.search(line)):
            printed.append((_js_frame(len(printed), v8["function"], v8["location"] or v8["bare"]),
                            bool(v8["async"])))
        elif firefox and _JS_LOCATION_END.search(line):
            name = firefox["function"]
            printed.append((_js_frame(len(printed), name.removeprefix("async*"),
                                      firefox["location"]), name.startswith("async*")))
        elif skipped := _NODE_OMITTED.match(line):
            omitted += int(skipped["count"])
        elif not line.strip():
            continue
        elif printed:
            ended = True
            unrecognized += 1
        else:
            header.append(line)
    # The error line is the first header line shaped like "Type: message"; source
    # excerpts that Node prints above it are not part of the error text.
    start = next((i for i, line in enumerate(header)
                  if (match := _HEADER.match(line.strip())) and match["value"] is not None), None)
    kind = value = None
    if start is not None:
        kind, value = _header(header[start])
        extra = [line.strip() for line in header[start + 1:]]
        value = "\n".join([value or "", *extra]).strip("\n") or None
        if start:
            builder.limitations.append(f"{start} line(s) above the error message were not interpreted")
    elif header:
        value = "\n".join(line.strip() for line in header)
    ordered = list(reversed(printed))
    frames = []
    for index, (frame, _) in enumerate(ordered):
        # An async caller frame means its callee resumed across an asynchronous boundary.
        frame.after_async_boundary = index > 0 and ordered[index - 1][1]
        frames.append(frame)
    if unrecognized:
        builder.limitations.append(
            f"{unrecognized} line(s) after the stack, such as a printed cause or error properties, "
            "were not interpreted")
    return [RawException(type=kind, value=value, frames=frames, frames_omitted=omitted)], [
        "V8 and Firefox print the most recent call first; frames were reversed to oldest caller first.",
        "Only the first error and its own stack are parsed; printed causes and aggregate members are not.",
    ]


def _dotnet(lines: list[str], builder: ObservationBuilder) -> tuple[list[RawException], list[str]]:
    first_frame = next(i for i, line in enumerate(lines) if _DOTNET_FRAME.match(line))
    header = [line.strip() for line in lines[:first_frame] if line.strip()]
    start = next((i for i, line in enumerate(header)
                  if (match := _HEADER.match(line)) and match["value"] is not None
                  and "." in match["type"]), 0)
    if start:
        builder.limitations.append(f"{start} line(s) above the exception header were not interpreted")
    chain = [_header(part) for part in _DOTNET_ARROW.split("\n".join(header[start:])) if part.strip()]
    segments: list[list[RawFrame]] = [[]]
    position = unrecognized = 0
    for line in lines[first_frame:]:
        if match := _DOTNET_FRAME.match(line):
            module, _, name = match["method"].rpartition(".")
            segments[-1].append(RawFrame(
                provider_index=position, function=name, module=module or None, path=match["path"],
                line=int(match["line"]) if match["line"] else None))
            position += 1
        elif _DOTNET_INNER_END.match(line):
            segments.append([])
        elif _DOTNET_ASYNC.match(line):
            # Printed newest first: the frame above the marker resumed after the boundary.
            if segments[-1]:
                segments[-1][-1].after_async_boundary = True
        elif line.strip():
            unrecognized += 1
    outer_first = [RawException(type=kind, value=value) for kind, value in chain] or [RawException()]
    # Segments print innermost exception first; the final segment belongs to the outer exception.
    for record, segment in zip(outer_first, reversed(segments)):
        record.frames = list(reversed(segment))
    if len(segments) > len(outer_first):
        unassigned = sum(len(segment) for segment in segments[:len(segments) - len(outer_first)])
        builder.limitations.append(
            f"{unassigned} frame(s) belong to stack segments without a matching exception header "
            "and were not assigned")
    ordered = list(reversed(outer_first))
    for record in ordered[:-1]:
        record.relation_to_next = "inner_exception"
    missing = sum(1 for record in ordered for frame in record.frames if frame.path is None)
    if missing:
        builder.limitations.append(
            f"{missing} frame(s) have no file or line; debug symbols may be unavailable")
    if unrecognized:
        builder.limitations.append(f"{unrecognized} line(s) in the stack were not interpreted")
    return ordered, [
        ".NET prints the most recent call first; frames were reversed to oldest caller first.",
        ("The header lists the outer exception first and inner exceptions after '--->'; records "
        "were reordered innermost (oldest) first."),
        "Each 'End of inner exception stack trace' marker ends the stack of the next inner exception.",
    ]


def normalize_stack_text(text: str, limits: DebuggingLimits | None = None) -> Observation:
    limits = limits or DebuggingLimits()
    if len(text.encode("utf-8", errors="replace")) > limits.max_payload_bytes:
        raise NormalizationError("Stack text exceeds the byte budget")
    builder = ObservationBuilder(limits)
    raw_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if any(len(line) > MAX_LINE_CHARS for line in raw_lines):
        raise NormalizationError(f"Stack lines must be at most {MAX_LINE_CHARS} characters")
    lines = raw_lines
    stack_format = detect_format(lines)
    parse = {"python_traceback": _python, "javascript_stack": _javascript,
             "dotnet_stack": _dotnet}[stack_format]
    exceptions, interpretation = parse(lines, builder)
    if not exceptions or not any(record.frames or record.type for record in exceptions):
        raise NormalizationError("No exception or stack frames were found")
    builder.limitations.append(
        "Pasted text carries no event identity, timestamp, environment, release or in-app markers")
    newest = exceptions[-1]
    summary = str(newest.value).split("\n", 1)[0] if newest.value else None
    title = ": ".join(part for part in (newest.type, summary) if part) or None
    source = ObservationSource(provider="pasted", format=stack_format, interpretation=interpretation)
    return builder.build(source, exceptions, title=title)
