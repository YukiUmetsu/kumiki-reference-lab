"""Generic batch loop: ordered or pooled work, resume predicate, atomic index.

The loop knows nothing about any site: items are opaque to it, record rows and
index payloads come from caller-supplied callables, and every failure is
converted into one index row instead of aborting the batch.
"""

from __future__ import annotations

import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from .store import write_json_atomic


@dataclass(frozen=True)
class BatchOutcome:
    """Counts and timing for one finished batch."""

    measured: int
    skipped: int
    failed: int
    attempted: int
    elapsed_seconds: float
    index_path: Path


def safe_error(
    error: Exception, *, redact: Iterable[str] = (), limit: int = 300,
) -> str:
    """Render an exception as bounded text with URLs, paths, and secrets gone."""
    text = f"{type(error).__name__}: {error}"
    text = re.sub(r"https?://\S+", "[redacted-url]", text)
    for value in redact:
        if isinstance(value, str) and value:
            text = text.replace(value, "[redacted]")
    text = re.sub(r"/[^\s:'\"]*kumiki-acquire-[^\s:'\"]*", "[scratch]", text)
    return text[:limit]


def run_batch(
    items: Iterable[Any], *,
    run_one: Callable[[Any], dict[str, Any]],
    index_path: Path,
    build_index: Callable[
        [list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]],
        dict[str, Any]],
    summary_row: Callable[[dict[str, Any]], dict[str, Any]],
    skip_row: Callable[[Any, str], dict[str, Any]],
    describe: Callable[[Any], str] = str,
    failure_row: Callable[[Any, str], dict[str, Any]] | None = None,
    skip_reason: Callable[[Any], str | None] | None = None,
    initial_skips: Iterable[dict[str, Any]] = (),
    error_text: Callable[[Exception], str] | None = None,
    progress: Callable[[int, int, str, str, str], None] | None = None,
    jobs: int = 1,
    delay_seconds: float = 0.0,
    jitter: Callable[[float], float] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> BatchOutcome:
    """Run one batch over opaque items and keep an atomic index current.

    ``skip_reason`` returns a caller-formatted reason (e.g. an existing-record
    resume check) or ``None`` to run the item. In sequential mode the loop
    sleeps ``delay_seconds`` plus equal jitter between items; pooled mode runs
    up to ``jobs`` items concurrently. Every item failure becomes one failure
    row, so one bad item never aborts the batch.

    ``progress`` receives ``(position, total, status, label, detail)`` and is
    called from the worker thread under no lock; it must not raise.
    """
    if type(jobs) is not int or jobs < 1:
        raise ValueError("jobs must be a positive integer")
    if not isinstance(delay_seconds, (int, float)) or delay_seconds < 0:
        raise ValueError("delay_seconds must be a non-negative number")
    delay = float(delay_seconds)
    jitter_fn = jitter if jitter is not None else (
        lambda base: random.uniform(0, base))
    error_fn = error_text if error_text is not None else safe_error
    payloads = list(items)
    lock = threading.Lock()
    measured: list[dict[str, Any]] = []
    skips: list[dict[str, Any]] = list(initial_skips)
    failures: list[dict[str, Any]] = []
    attempted = 0
    started = time.monotonic()

    def refresh() -> None:
        write_json_atomic(
            index_path, build_index(list(measured), list(skips), list(failures)))

    work: list[Any] = []
    for item in payloads:
        reason = skip_reason(item) if skip_reason is not None else None
        if reason is not None:
            skips.append(skip_row(item, reason))
        else:
            work.append(item)
    refresh()

    def handle(item: Any) -> None:
        nonlocal attempted
        with lock:
            attempted += 1
            position = attempted
        label = describe(item)
        try:
            record = run_one(item)
        except Exception as error:  # one bad item must not abort the batch
            reason = error_fn(error)
            with lock:
                failures.append(
                    (failure_row or skip_row)(item, reason))
                refresh()
            if progress is not None:
                progress(position, len(work), "fail", label, reason)
            return
        with lock:
            measured.append(summary_row(record))
            refresh()
        if progress is not None:
            progress(position, len(work), "ok", label, "")

    if jobs == 1:
        for position, item in enumerate(work):
            handle(item)
            if delay and position + 1 < len(work):
                sleeper(delay + jitter_fn(delay))
    else:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            futures = [pool.submit(handle, item) for item in work]
            for future in as_completed(futures):
                future.result()
    refresh()

    return BatchOutcome(
        measured=len(measured),
        skipped=len(skips),
        failed=len(failures),
        attempted=attempted,
        elapsed_seconds=round(time.monotonic() - started, 3),
        index_path=index_path,
    )
