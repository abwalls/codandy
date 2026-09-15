"""Disposable native-parser process; only our analyzer code is executed."""

import multiprocessing
import time
from pathlib import Path

from pydantic import ValidationError

from app.ingestion import IngestionError
from app.models import AtlasDocument
from app.settings import Settings
from app.structure.models import EXTRACTION_FAILED, StructureDocument

# Diagram extraction stops once this share of the analysis budget has elapsed, so the parent's
# hard deadline never discards a finished atlas because of diagrams.
STRUCTURE_BUDGET = 0.85


def _analyze(connection, root, url, ref, limits):
    from app.analyzer import analyze_repository
    from app.structure.extract import build_structure

    started = time.monotonic()
    try:
        settings = Settings.model_validate(limits)
        atlas = analyze_repository(Path(root), url, ref, settings,
                                   lambda phase, value: connection.send(("progress", phase, value)))
        connection.send(("progress", "reporting", 89))
        structure = build_structure(Path(root), atlas, settings,
                                    started + settings.analysis_timeout_seconds * STRUCTURE_BUDGET)
        connection.send(("result", atlas.model_dump_json(), structure.model_dump_json()))
    except IngestionError as exc:
        connection.send(("error", str(exc)))
    except Exception:  # noqa: BLE001 - sanitize errors across the worker boundary
        connection.send(("error", "Static analysis failed"))
    finally:
        connection.close()


def analyze_isolated(root, url, ref, limits, progress, *,
                     worker=_analyze) -> tuple[AtlasDocument, StructureDocument]:
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=worker, args=(sender, str(root), url, ref,
                                                  limits.model_dump()), daemon=True)
    deadline = time.monotonic() + limits.analysis_timeout_seconds
    try:
        process.start()
        sender.close()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise IngestionError("Static analysis timed out")
            if receiver.poll(min(0.05, remaining)):
                try:
                    message = receiver.recv()
                except EOFError as exc:
                    raise IngestionError("Static analysis worker exited unexpectedly") from exc
                if message[0] == "progress":
                    progress(message[1], message[2])
                elif message[0] == "error":
                    raise IngestionError(message[1])
                elif message[0] == "result":
                    atlas = AtlasDocument.model_validate_json(message[1])
                    try:
                        structure = StructureDocument.model_validate_json(message[2])
                    except (IndexError, ValidationError):
                        structure = StructureDocument(limitations=[EXTRACTION_FAILED])
                    return atlas, structure
            elif not process.is_alive():
                raise IngestionError("Static analysis worker exited unexpectedly")
    finally:
        sender.close()
        receiver.close()
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
            process.join(timeout=2)
            if process.is_alive():
                process.kill()
                process.join()
            process.close()
