"""Disposable native-parser process; only our analyzer code is executed."""

import multiprocessing
import time
from pathlib import Path

from app.ingestion import IngestionError
from app.models import AtlasDocument
from app.settings import Settings


def _analyze(connection, root, url, ref, limits):
    from app.analyzer import analyze_repository

    try:
        atlas = analyze_repository(Path(root), url, ref, Settings.model_validate(limits),
                                   lambda phase, value: connection.send(("progress", phase, value)))
        connection.send(("result", atlas.model_dump_json()))
    except IngestionError as exc:
        connection.send(("error", str(exc)))
    except Exception:  # noqa: BLE001 - sanitize errors across the worker boundary
        connection.send(("error", "Static analysis failed"))
    finally:
        connection.close()


def analyze_isolated(root, url, ref, limits, progress, *, worker=_analyze):
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
                    return AtlasDocument.model_validate_json(message[1])
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
