"""Private, explicit source identity/rights bindings for What Ships local footage.

This does not confer rights or verify a title's actual pictured contents.
The binding JSON contains local filesystem paths. Keep it outside Git.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import inspect_source, sha256_file
from kumiki_reference_lab.catalog.video_sources import _from_whatships, _load_snapshot
from kumiki_reference_lab.catalog.whatships_full_coverage import build_full_coverage
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.pipeline.ollama_character_perception import _VIDEO_EXTENSIONS

SCHEMA_VERSION = "kumiki.whatships-local-media-bindings.v1"
REPORT_VERSION = "kumiki.whatships-local-media-coverage.v1"
_RIGHTS = frozenset({"own-original-work", "written-permission",
                     "permissive-license", "other-lawful-authorization"})
_MAX_FILES = 3000
_MAX_MANIFEST_BYTES = 2_000_000
_MAX_MEDIA_BYTES = 12 * 1024 * 1024 * 1024
_SHA = re.compile(r"[0-9a-f]{64}\Z")


def _read_json(path: Path) -> Any:
    if (path.is_symlink() or not path.is_file() or
            path.stat().st_size > _MAX_MANIFEST_BYTES):
        raise ValueError("local media binding manifest must be a regular JSON <= 2 MiB")
    try:
        return json.loads(path.read_text(encoding="utf-8"),
                          object_pairs_hook=_unique_json,
                          parse_constant=lambda s: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("media binding manifest is invalid UTF-8 JSON") from exc


def _unique_json(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for key, value in pairs:
        if key in data:
            raise ValueError("duplicate media binding JSON property")
        data[key] = value
    return data


def _video_identity_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    # The source catalog validates canonical URLs, slugs and category provenance.
    _from_whatships(snapshot)
    return {"whatships:" + row["slug"]: row for row in snapshot["videos"]}


def _media_path(value: Any) -> Path:
    if type(value) is not str or not 2 <= len(value) <= 4096 or "\x00" in value:
        raise ValueError("media path must be an explicit local absolute path")
    path = Path(value)
    if (not path.is_absolute() or path.is_symlink() or
            not path.is_file() or path.suffix.lower() not in _VIDEO_EXTENSIONS):
        raise ValueError("bound media must be a regular supported local video, not a symlink/URL")
    stat = path.stat()
    if not 0 < stat.st_size <= _MAX_MEDIA_BYTES:
        raise ValueError("media file is empty or exceeds local media size limit")
    return path


def _binding_schema(value: Any, source_map: dict[str, dict[str, Any]]) -> None:
    if not isinstance(value, dict) or set(value) != {
            "sourceId", "watchUrl", "localPath", "mediaSha256",
            "mediaSizeBytes", "sourceStreamIndex", "sourceTimebase",
            "rightsBasis", "rightsNote", "identityNote",
            "rightsStatus", "verificationStatus", "boundOn"}:
        raise ValueError("media binding contains missing or unrecognized fields")
    source_id = value["sourceId"]
    if type(source_id) is not str or source_id not in source_map:
        raise ValueError("media binding refers to an unknown What Ships ID")
    if value["watchUrl"] != source_map[source_id]["directoryUrl"]:
        raise ValueError("media binding canonical source URL does not match catalog")
    if type(value["localPath"]) is not str or not Path(value["localPath"]).is_absolute():
        raise ValueError("media binding must use an absolute local file path")
    if not isinstance(value["mediaSha256"], str) or not _SHA.fullmatch(value["mediaSha256"]):
        raise ValueError("media binding requires SHA256 of local video bytes")
    if (type(value["mediaSizeBytes"]) is not int or
            not 0 < value["mediaSizeBytes"] <= _MAX_MEDIA_BYTES):
        raise ValueError("media binding recorded file size invalid")
    if type(value["sourceStreamIndex"]) is not int or not 0 <= value["sourceStreamIndex"] <= 64:
        raise ValueError("media binding source stream invalid")
    tb = value["sourceTimebase"]
    if (not isinstance(tb, dict) or set(tb) != {"numerator", "denominator"} or
            type(tb["numerator"]) is not int or type(tb["denominator"]) is not int or
            tb["numerator"] <= 0 or tb["denominator"] <= 0):
        raise ValueError("media binding original source timebase invalid")
    if type(value["rightsBasis"]) is not str or value["rightsBasis"] not in _RIGHTS:
        raise ValueError("unsupported media rights declaration")
    if not all(type(value[field]) is str and 12 <= len(value[field].strip()) <= 500
               for field in ("rightsNote", "identityNote")):
        raise ValueError("media rights and source-identification notes must be explicit")
    if (value["rightsStatus"] != "user-declared-authorized" or
            value["verificationStatus"] != "operator-attestation-not-independently-verified"):
        raise ValueError("media binding must not claim independent authorization or identity verification")
    if type(value["boundOn"]) is not str:
        raise ValueError("media binding date missing")
    try:
        if date.fromisoformat(value["boundOn"]).isoformat() != value["boundOn"]:
            raise ValueError
    except ValueError:
        raise ValueError("media binding date is not ISO YYYY-MM-DD") from None


def load_media_bindings(manifest: Path, snapshot: dict[str, Any], *,
                        verify_files: bool = False) -> dict[str, Any]:
    doc = _read_json(manifest)
    if not isinstance(doc, dict) or set(doc) != {
            "schemaVersion", "createdOn", "catalogIndexUrl", "bindings",
            "disclaimer"} or doc["schemaVersion"] != SCHEMA_VERSION:
        raise ValueError("unsupported local media binding manifest schema")
    if doc["catalogIndexUrl"] != "https://whatships.com/search-index.json":
        raise ValueError("local media bindings refer to the wrong catalog")
    try:
        if date.fromisoformat(doc["createdOn"]).isoformat() != doc["createdOn"]:
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError("media binding manifest createdOn date invalid") from None
    if (doc["disclaimer"] != "self-declared-source-identity-and-authorization-only" or
            not isinstance(doc["bindings"], list) or len(doc["bindings"]) > _MAX_FILES):
        raise ValueError("media binding count or attestation declaration invalid")
    source_map = _video_identity_map(snapshot)
    known_ids, known_hashes = set(), set()
    for row in doc["bindings"]:
        _binding_schema(row, source_map)
        if row["sourceId"] in known_ids or row["mediaSha256"] in known_hashes:
            raise ValueError("media binding duplicates a What Ships ID or reuses an unrelated media fingerprint")
        known_ids.add(row["sourceId"])
        known_hashes.add(row["mediaSha256"])
        if verify_files:
            path = _media_path(row["localPath"])
            signature = file_signature(path)
            if (path.stat().st_size != row["mediaSizeBytes"] or
                    sha256_file(path) != row["mediaSha256"]):
                raise ValueError("local bound media file differs from registered source SHA/size")
            require_unchanged(path, signature)
    return doc


def _empty_manifest() -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "createdOn": date.today().isoformat(),
        "catalogIndexUrl": "https://whatships.com/search-index.json",
        "disclaimer": "self-declared-source-identity-and-authorization-only",
        "bindings": [],
    }


def _write_new_folder(out: Path, items: dict[str, Any]) -> None:
    if out.exists() or out.is_symlink():
        raise ValueError("binding output must be a new directory")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".kumiki-whatships-media-", dir=out.parent) as temp:
        stage = Path(temp)
        for name, value in items.items():
            (stage/name).write_text(
                json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+"\n",
                encoding="utf-8")
        if out.exists() or out.is_symlink():
            raise ValueError("media binding output path became occupied")
        os.replace(stage, out)


def register_local_media(
    snapshot_path: Path, video: Path, source_id: str, out: Path, *,
    rights_basis: str, rights_note: str, identity_note: str,
    acknowledge_rights: bool = False, previous: Path | None = None,
    ffprobe: str = "ffprobe",
) -> Path:
    """Record one explicitly attested source/media match in a PRIVATE ledger."""
    if acknowledge_rights is not True:
        raise ValueError("user must explicitly acknowledge lawful source rights and video identity")
    if type(rights_basis) is not str or rights_basis not in _RIGHTS:
        raise ValueError("rights basis must be an explicit supported declaration")
    if not all(type(note) is str and 12 <= len(note.strip()) <= 500
               for note in (rights_note, identity_note)):
        raise ValueError("provide clear rights and catalog-matching evidence notes (12..500 chars)")
    if out.exists() or out.is_symlink():
        raise ValueError("binding output must be a new directory")
    snapshot_sig = file_signature(snapshot_path)
    snapshot = _load_snapshot(snapshot_path)
    source_map = _video_identity_map(snapshot)
    if source_id not in source_map:
        raise ValueError("cannot bind media to an unknown indexed What Ships video")
    previous_sig = file_signature(previous) if previous is not None else None
    doc = (load_media_bindings(previous, snapshot, verify_files=False)
           if previous is not None else _empty_manifest())
    if len(doc["bindings"]) >= _MAX_FILES:
        raise ValueError("media binding manifest reached maximum capacity")
    if any(x["sourceId"] == source_id for x in doc["bindings"]):
        raise ValueError("media source is already bound; do not silently replace identity/rights")
    video = _media_path(str(video.absolute()))
    signature = file_signature(video)
    info = inspect_source(video, ffprobe=ffprobe, rights_status="user-declared-authorized")
    if info["source"]["sizeBytes"] != signature[0]:
        raise ValueError("local media source changed during probing")
    require_unchanged(video, signature)
    if any(row["mediaSha256"] == info["source"]["sha256"] for row in doc["bindings"]):
        raise ValueError("same local video content already mapped to a different catalog entry")
    row = {
        "sourceId": source_id,
        "watchUrl": source_map[source_id]["directoryUrl"],
        "localPath": str(video.resolve(strict=True)),
        "mediaSha256": info["source"]["sha256"],
        "mediaSizeBytes": signature[0],
        "sourceStreamIndex": info["video"]["streamIndex"],
        "sourceTimebase": info["video"]["sourceTimebase"],
        "rightsBasis": rights_basis,
        "rightsNote": rights_note.strip(),
        "identityNote": identity_note.strip(),
        "rightsStatus": "user-declared-authorized",
        "verificationStatus": "operator-attestation-not-independently-verified",
        "boundOn": date.today().isoformat(),
    }
    doc = {**doc, "bindings": doc["bindings"] + [row]}
    _binding_schema(row, source_map)
    require_unchanged(video, signature)
    require_unchanged(snapshot_path, snapshot_sig)
    if previous is not None and previous_sig is not None:
        require_unchanged(previous, previous_sig)
    # A deliberately separate, REDACTED summary avoids exposing absolute local
    # file paths when sharing queue/coverage reports.
    report = summarize_bound_coverage(snapshot, doc, physical_verification="newly-probed")
    _write_new_folder(out, {"media-bindings.json": doc, "coverage.json": report})
    return out/"media-bindings.json"


def summarize_bound_coverage(snapshot: dict[str, Any], doc: dict[str, Any], *,
                             physical_verification: str) -> dict[str, Any]:
    source_map = _video_identity_map(snapshot)
    counts = Counter()
    by_category: dict[str, int] = Counter()
    for entry in doc["bindings"]:
        _binding_schema(entry, source_map)
        counts["bound"] += 1
        category = source_map[entry["sourceId"]]["indexMetadata"].rsplit(" · ", 1)[-1]
        by_category[category] += 1
    coverage, _ = build_full_coverage(snapshot)
    return {
        "schemaVersion": REPORT_VERSION,
        "snapshotOn": snapshot["retrievedOn"],
        "indexedVideoCount": coverage["totalVideoEntries"],
        "boundMediaCount": counts["bound"],
        "unboundVideoCount": coverage["totalVideoEntries"]-counts["bound"],
        "boundByCategory": dict(sorted(by_category.items())),
        "physicalVerification": physical_verification,
        "identityAndRightsStatus": "operator-attested-not-third-party-confirmed",
        "actuallyAnalyzedVideoCount": 0,
        "humanReviewedVideoCount": 0,
        "limitations": [
            "Linked media files were mapped to catalog entries by explicit operator assertion, not visual identity proof.",
            "Lawful rights basis is user-declared and not legally adjudicated.",
            "No source video frame, camera movement, lighting, speech or character analysis is implied.",
            "Private binding JSON contains sensitive absolute local file paths; do not commit or publish it.",
        ],
    }


def media_coverage(snapshot_path: Path, manifest_path: Path, *,
                   verify_files: bool = False) -> dict[str, Any]:
    snapshot = _load_snapshot(snapshot_path)
    bindings = load_media_bindings(manifest_path, snapshot, verify_files=verify_files)
    return summarize_bound_coverage(snapshot, bindings,
                                    physical_verification=("sha256-rechecked" if verify_files
                                                           else "not-performed"))


def eligible_bound_media(snapshot_path: Path, manifest_path: Path, *,
                         limit: int = 20) -> dict[str, Any]:
    """Return a privacy-safe plan for files that really exist at their registered SHA."""
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("eligible media batch limit must be 1..100")
    snapshot = _load_snapshot(snapshot_path)
    doc = load_media_bindings(manifest_path, snapshot, verify_files=True)
    indexed = _video_identity_map(snapshot)
    candidates = []
    for row in doc["bindings"][:limit]:
        entry = indexed[row["sourceId"]]
        candidates.append({
            "sourceId": row["sourceId"],
            "watchUrl": row["watchUrl"],
            "category": entry["indexMetadata"].rsplit(" · ", 1)[-1],
            "localMediaSha256": row["mediaSha256"],
            "rightsStatus": row["rightsStatus"],
            "sourceIdentityStatus": row["verificationStatus"],
            "nextStage": "eligible-for-bounded-local-inference-not-yet-analyzed",
        })
    return {
        "schemaVersion": "kumiki.whatships-local-analysis-queue.v1",
        "snapshotOn": snapshot["retrievedOn"],
        "eligibleVerifiedBindings": len(doc["bindings"]),
        "returnedCount": len(candidates),
        "entries": candidates,
        "methodLimits": [
            "This queue verifies media byte fingerprints, not copyright ownership or visual source identity.",
            "No visual inference or camera/lighting measurement was performed by the queue.",
            "Absolute local paths are intentionally excluded; use the private binding manifest to run analysis.",
        ],
    }
