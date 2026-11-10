"""Small, source-hashed real-footage calibration set; no footage is distributed."""

from __future__ import annotations

import json
import math
import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from kumiki_reference_lab.analyzers.media.inspect import inspect_source
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged


SCHEMA_VERSION = "kumiki.open-footage-calibration.v1"
_ID = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
_FILE = re.compile(r"[a-z][a-z0-9-]*\.(?:webm|mp4|mov|mkv)\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_LICENSES = {
    "CC-BY-3.0": "https://creativecommons.org/licenses/by/3.0/",
    "CC-BY-SA-4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
}
_TAGS = {"paper-cut", "kinetic-typography", "2d-motion-graphics", "3d-rendered",
         "title-card", "stop-motion", "character-animation", "unclassified"}


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate open-footage JSON property: {key}")
        result[key] = value
    return result


def validate_open_footage(document: Any) -> list[str]:
    errors: list[str] = []

    def obj(raw: Any, expected: set[str], prefix: str) -> dict[str, Any]:
        if not isinstance(raw, dict):
            errors.append(f"{prefix} must be an object")
            return {}
        for field in sorted(expected - raw.keys()):
            errors.append(f"{prefix}.{field} missing")
        for field in sorted(raw.keys() - expected):
            errors.append(f"{prefix}.{field} unexpected")
        return raw

    def bounded_text(raw: Any, prefix: str) -> None:
        if not isinstance(raw, str) or not 4 <= len(raw.strip()) <= 500:
            errors.append(f"{prefix} requires 4..500 characters")

    def url(raw: Any, prefix: str, *, allowed_host: str | None = None) -> None:
        try:
            parsed = urlsplit(raw)
            if (parsed.scheme != "https" or not parsed.hostname or
                    parsed.username is not None or parsed.password is not None or
                    parsed.port not in (None, 443) or parsed.fragment or
                    (allowed_host is not None and parsed.hostname != allowed_host)):
                raise ValueError
        except (TypeError, ValueError, AttributeError):
            errors.append(f"{prefix} must be a safe HTTPS URL")

    root = obj(document, {"schemaVersion", "collectedOn", "methodology", "entries"}, "dataset")
    if root.get("schemaVersion") != SCHEMA_VERSION:
        errors.append("dataset.schemaVersion unsupported")
    try:
        if type(root.get("collectedOn")) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", root["collectedOn"]):
            raise ValueError
        date.fromisoformat(root["collectedOn"])
    except (TypeError, ValueError, KeyError):
        errors.append("dataset.collectedOn must be an ISO date")
    bounded_text(root.get("methodology"), "dataset.methodology")
    entries = root.get("entries")
    if not isinstance(entries, list) or not 1 <= len(entries) <= 100:
        errors.append("dataset.entries requires 1..100 records")
        return errors
    seen_ids: set[str] = set()
    seen_files: set[str] = set()
    seen_hashes: set[str] = set()
    for idx, raw in enumerate(entries):
        prefix = f"entries[{idx}]"
        item = obj(raw, {"id", "title", "creator", "rights", "media", "sample",
                         "frameObservations", "audienceStatus"}, prefix)
        identifier = item.get("id")
        if not isinstance(identifier, str) or not _ID.fullmatch(identifier):
            errors.append(f"{prefix}.id invalid")
        elif identifier in seen_ids:
            errors.append(f"{prefix}.id duplicated")
        else:
            seen_ids.add(identifier)
        for field in ("title", "creator"):
            bounded_text(item.get(field), f"{prefix}.{field}")
        if item.get("audienceStatus") != "not-measured-for-this-file":
            errors.append(f"{prefix}.audienceStatus cannot claim audience evidence")
        rights = obj(item.get("rights"), {"commonsPage", "license", "licenseUrl", "attribution"},
                     f"{prefix}.rights")
        url(rights.get("commonsPage"), f"{prefix}.rights.commonsPage", allowed_host="commons.wikimedia.org")
        bounded_text(rights.get("attribution"), f"{prefix}.rights.attribution")
        license_id = rights.get("license")
        if (not isinstance(license_id, str) or license_id not in _LICENSES or
                rights.get("licenseUrl") != _LICENSES[license_id]):
            errors.append(f"{prefix}.rights license mismatch or unsupported")
        media = obj(item.get("media"), {"localName", "downloadUrl", "sha256", "sizeBytes",
                                      "durationMilliseconds", "width", "height", "streamIndex",
                                      "sourceTimebase"}, f"{prefix}.media")
        name = media.get("localName")
        if not isinstance(name, str) or not _FILE.fullmatch(name):
            errors.append(f"{prefix}.media.localName must be a simple media filename")
        elif name in seen_files:
            errors.append(f"{prefix}.media.localName duplicated")
        else:
            seen_files.add(name)
        url(media.get("downloadUrl"), f"{prefix}.media.downloadUrl", allowed_host="commons.wikimedia.org")
        sha = media.get("sha256")
        if not isinstance(sha, str) or not _SHA.fullmatch(sha):
            errors.append(f"{prefix}.media.sha256 invalid")
        elif sha in seen_hashes:
            errors.append(f"{prefix}.media.sha256 duplicated")
        else:
            seen_hashes.add(sha)
        for field, minimum, maximum in (("sizeBytes", 1, 2_000_000_000),
                                        ("durationMilliseconds", 1000, 7_200_000),
                                        ("width", 32, 8192), ("height", 32, 8192)):
            value = media.get(field)
            if type(value) is not int or not minimum <= value <= maximum:
                errors.append(f"{prefix}.media.{field} invalid")
        stream_index = media.get("streamIndex")
        if type(stream_index) is not int or not 0 <= stream_index <= 16:
            errors.append(f"{prefix}.media.streamIndex invalid")
        base = obj(media.get("sourceTimebase"), {"numerator", "denominator"},
                   f"{prefix}.media.sourceTimebase")
        if (type(base.get("numerator")) is not int or not 1 <= base["numerator"] <= 1_000_000_000 or
                type(base.get("denominator")) is not int or not 1 <= base["denominator"] <= 1_000_000_000):
            errors.append(f"{prefix}.media.sourceTimebase must have positive bounded integer components")
        sample = obj(item.get("sample"), {"startSeconds", "requestedSeconds", "imageMotion",
                                           "displayLuma"}, f"{prefix}.sample")
        if type(sample.get("startSeconds")) is not int or sample["startSeconds"] != 0:
            errors.append(f"{prefix}.sample.startSeconds must be 0 (current pipeline limit)")
        requested = sample.get("requestedSeconds")
        if type(requested) is not int or not 1 <= requested <= 30:
            errors.append(f"{prefix}.sample.requestedSeconds must be 1..30")
        for field in ("imageMotion", "displayLuma"):
            measure = obj(sample.get(field), {"activeRuns", "cutCandidates", "sampledSpanSeconds",
                                              "measuredPairFraction", "activeTimeFractionOfMeasured"},
                          f"{prefix}.sample.{field}")
            for key in ("activeRuns", "cutCandidates"):
                value = measure.get(key)
                if type(value) is not int or not 0 <= value <= 1000:
                    errors.append(f"{prefix}.sample.{field}.{key} invalid")
            for key, low, high in (("sampledSpanSeconds", 0.01,
                                    requested + 0.2 if type(requested) is int and requested > 0 else 30.2),
                                   ("measuredPairFraction", 0.0, 1.0),
                                   ("activeTimeFractionOfMeasured", 0.0, 1.0)):
                value = measure.get(key)
                if (type(value) not in (float, int) or not math.isfinite(value)
                        or not low <= value <= high):
                    errors.append(f"{prefix}.sample.{field}.{key} invalid")
        observed = obj(item.get("frameObservations"), {"reviewMode", "sampledWindowNote",
                                                        "secondaryFrameNote", "visibleTags"},
                       f"{prefix}.frameObservations")
        if observed.get("reviewMode") != "contact-sheets-only-no-full-speed-viewing":
            errors.append(f"{prefix}.frameObservations.reviewMode must not assert human playback")
        bounded_text(observed.get("sampledWindowNote"), f"{prefix}.frameObservations.sampledWindowNote")
        bounded_text(observed.get("secondaryFrameNote"), f"{prefix}.frameObservations.secondaryFrameNote")
        tags = observed.get("visibleTags")
        if (not isinstance(tags, list) or not 1 <= len(tags) <= 5 or
                any(not isinstance(tag, str) or tag not in _TAGS for tag in tags) or
                len(tags) != len(set(tags))):
            errors.append(f"{prefix}.frameObservations.visibleTags invalid")
    return errors


def load_open_footage(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 262_144:
        raise ValueError("open-footage dataset must be regular JSON of at most 256 KiB")
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError(f"invalid open-footage JSON: {exc}") from exc
    errors = validate_open_footage(data)
    if errors:
        raise ValueError("invalid open-footage dataset:\n" + "\n".join(errors))
    return data


def verify_open_footage_media(dataset: dict[str, Any], media_root: Path, *,
                              ffprobe: str = "ffprobe", reference_id: str | None = None) -> dict[str, Any]:
    """Verify local source bytes and probe facts; never retrieve media or certify the license."""
    if errors := validate_open_footage(dataset):
        raise ValueError("invalid open-footage dataset: " + errors[0])
    if not media_root.is_dir() or media_root.is_symlink():
        raise ValueError("media root must be a regular existing directory")
    selected = [item for item in dataset["entries"] if reference_id is None or item["id"] == reference_id]
    if not selected:
        raise ValueError("reference ID not found")
    verified: list[dict[str, Any]] = []
    for item in selected:
        expected = item["media"]
        path = media_root / expected["localName"]
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"missing regular media file for {item['id']}")
        # inspect_source hashes the bytes and probes the first real video stream.
        signature = file_signature(path)
        actual = inspect_source(path, ffprobe=ffprobe)
        require_unchanged(path, signature)
        source = actual["source"]
        video = actual["video"]
        expected_duration_ms = expected["durationMilliseconds"]
        try:
            duration_ms = round(float(video["durationSecondsReported"]) * 1000)
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError(f"missing probed duration for {item['id']}") from exc
        if (source["sha256"] != expected["sha256"] or
                source["sizeBytes"] != expected["sizeBytes"] or
                abs(duration_ms - expected_duration_ms) > 2 or
                video["streamIndex"] != expected["streamIndex"] or
                video["width"] != expected["width"] or
                video["height"] != expected["height"] or
                video["sourceTimebase"] != expected["sourceTimebase"]):
            raise ValueError(f"media bytes or probe metadata do not match reference {item['id']}")
        verified.append({"id": item["id"], "localName": expected["localName"],
                         "sha256": source["sha256"], "verified": True})
    return {"verifiedLocalMedia": True, "count": len(verified), "references": verified,
            "limits": "File/probe verification only; no rights, visual-style or audience certification."}
