"""Offline, accessible visual timeline of source-linked candidate edit evidence.

This report is a *measurement viewer*, not an audio/video sync calibration,
sequence editor, semantic classifier or independently recovered camera path.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.audio.av_cuts import av_cut_evidence_from_levels
from kumiki_reference_lab.analyzers.audio.levels import analyze_audio_levels
from kumiki_reference_lab.analyzers.audio.onsets import audio_onsets_from_levels
from kumiki_reference_lab.analyzers.media.inspect import sha256_file
from kumiki_reference_lab.analyzers.shots.evidence import build_shot_evidence
from kumiki_reference_lab.analyzers.shots.rhythm import edit_rhythm_from_verified_shots
from kumiki_reference_lab.analyzers.techniques.propose import _json_file
from kumiki_reference_lab.contracts.analysis import TIMELINE_REVIEW_VERSION
from kumiki_reference_lab.core.artifacts import write_json_artifact
from kumiki_reference_lab.pipeline.analyze import _file_records


STYLE_REVISION = "offline-observation-tracks-v2"


def _frac(value: dict[str, int]) -> Fraction:
    return Fraction(value["numerator"], value["denominator"])


def _sec(value: Fraction) -> str:
    return f"{float(value):.3f} s"


def _h(value: object) -> str:
    return html.escape(str(value), quote=True)


def _serialize(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _timing(evidence: dict[str, Any], rhythm: dict[str, Any],
            av: dict[str, Any], onsets: dict[str, Any]) -> tuple[Fraction, Fraction]:
    """Cross-check all report identities before placing them on one axis."""
    identity = (evidence["sourceSha256"], evidence["analysisRunSha256"])
    if (av["sourceSha256"], av["analysisRunSha256"]) != identity or (
            rhythm["sourceSha256"], rhythm["analysisRunSha256"]) != identity:
        raise ValueError("timeline evidence sources or analysis runs disagree")
    if (rhythm["sourceTimebase"] != evidence["sourceTimebase"] or
            av["videoSourceTimebase"] != evidence["sourceTimebase"] or
            rhythm["videoCutCandidateCount"] != av["videoCutCandidateCount"] or
            av["videoCutCandidateCount"] != len(evidence["regions"]) - 1):
        raise ValueError("timeline source clock or candidate cut counts disagree")
    if av["status"] not in ("no-audio-stream", "candidate-cross-stream-pts-association"):
        raise ValueError("timeline audio evidence has an unsupported status")
    if (av["status"] == "no-audio-stream" and av["cutCandidates"]) or (
            av["status"] == "candidate-cross-stream-pts-association" and
            [r["videoRegionId"] for r in av["cutCandidates"]] !=
            [r["id"] for r in evidence["regions"][1:]]):
        raise ValueError("timeline A/V candidate identities disagree")
    if (onsets["sourceSha256"] != evidence["sourceSha256"] or
            onsets["audioStreamIndex"] != av["audioStreamIndex"] or
            onsets["sourceTimebase"] != av["audioSourceTimebase"] or
            onsets["scanWindowSeconds"] != av["scanWindowSeconds"] or
            (onsets["status"] == "no-audio-stream") !=
            (av["status"] == "no-audio-stream") or
            onsets["status"] not in ("no-audio-stream",
                                    "source-pts-aligned-level-attack-candidates")):
        raise ValueError("timeline audio onset evidence identity or status disagrees")
    if (onsets["status"] == "no-audio-stream" and onsets["candidates"]):
        raise ValueError("timeline audio onset report contradicts absent audio")
    regions = evidence["regions"]
    if not regions:
        raise ValueError("timeline requires at least one source-timed region")
    first = _frac(regions[0]["startSeconds"])
    last = _frac(regions[-1]["lastObservedFrameSeconds"])
    if last < first:
        raise ValueError("timeline observed source range is negative")
    return first, last


def render_timeline_html(evidence: dict[str, Any], rhythm: dict[str, Any],
                         av: dict[str, Any], onsets: dict[str, Any], *,
                         source_label: str) -> str:
    """Render a self-contained SVG visualization + accessible evidence tables."""
    start, end = _timing(evidence, rhythm, av, onsets)
    span = end - start
    if span <= 0:
        span = Fraction(1, 1000)  # Display-only axis guard; not a measured duration.
    plot_left, plot_width = 202, 958

    def x(time: Fraction) -> float:
        return plot_left + float((time - start) / span) * plot_width

    pieces = []
    for i in range(6):
        tick = start + (end - start) * Fraction(i, 5)
        tx = x(tick)
        pieces.append(
            f'<line x1="{tx:.2f}" x2="{tx:.2f}" y1="55" y2="312" '
            'stroke="#2e4055" stroke-width="1"/>'
            f'<text x="{tx:.2f}" y="34" text-anchor="middle" '
            f'class="axis">{_h(_sec(tick))}</text>')
    pieces += [
        '<text x="12" y="99" class="track-label">Candidate regions</text>',
        '<text x="12" y="155" class="track-label">Image-plane motion</text>',
        '<text x="12" y="199" class="track-label">Cut-to-cut gaps</text>',
        '<text x="12" y="245" class="track-label">Audio near cuts</text>',
        '<text x="12" y="293" class="track-label">Audio level attacks</text>',
    ]
    regions = evidence["regions"]
    for index, region in enumerate(regions):
        a = _frac(region["startSeconds"])
        b = (_frac(regions[index + 1]["startSeconds"]) if index + 1 < len(regions)
             else _frac(region["lastObservedFrameSeconds"]))
        if b < a:
            raise ValueError("timeline candidate regions are out of order")
        bx, width = x(a), max(1.5, x(b) - x(a))
        shade = "#23465d" if index % 2 == 0 else "#1b3449"
        pieces.append(f'<rect x="{bx:.2f}" y="76" width="{width:.2f}" '
                      f'height="37" rx="3" fill="{shade}" stroke="#5b7a90"/>')
        if width > 70:
            pieces.append(f'<text x="{bx + 8:.2f}" y="100" '
                          f'class="region-label">{_h(region["id"])}</text>')
        motion = region["observations"]["motion"]
        value = (motion.get("meanGlobalImageDisplacementNormalized")
                 if isinstance(motion, dict) else None)
        if isinstance(value, (int, float)) and 0 <= value < float("inf"):
            # Numeric value maps only to apparent displacement per sampled
            # pair. Capped at 0.1; the figure never asserts camera speed.
            height = min(25.0, value * 250)
            pieces.append(f'<rect x="{bx:.2f}" y="{163-height:.2f}" '
                          f'width="{width:.2f}" height="{max(1,height):.2f}" '
                          'fill="#60bad2" opacity="0.8"/>')
    for item in rhythm["intervals"]:
        a, b = _frac(item["fromSeconds"]), _frac(item["toSeconds"])
        left, width = x(a), x(b) - x(a)
        pieces.append(f'<line x1="{left:.2f}" x2="{left+width:.2f}" y1="188" '
                      'y2="188" stroke="#e3af72" stroke-width="5"/>')
        if width > 55:
            pieces.append(f'<text x="{left+width/2:.2f}" y="178" '
                          'text-anchor="middle" class="interval-label">'
                          f'{_h(_sec(_frac(item["durationSeconds"])))}</text>')
    audio_by_region = {r["videoRegionId"]: r for r in av["cutCandidates"]}
    for region in regions[1:]:
        cut_x = x(_frac(region["startSeconds"]))
        pieces.append(f'<line x1="{cut_x:.2f}" x2="{cut_x:.2f}" '
                      'y1="69" y2="312" stroke="#f1b970" stroke-width="1.6" '
                      'stroke-dasharray="3 4"/>')
        signal = audio_by_region.get(region["id"])
        if signal is not None:
            marked = signal["status"] == "candidate-quiet-level-contrast"
            fill = "#d0a9f5" if marked else "#607389"
            pieces.append(f'<circle cx="{cut_x:.2f}" cy="234" r="6.5" '
                          f'fill="{fill}" stroke="#0b1420" stroke-width="2"/>')
    if av["status"] == "no-audio-stream":
        pieces.append('<text x="209" y="243" class="no-audio">No audio stream</text>')
        pieces.append('<text x="209" y="295" class="no-audio">No audio stream</text>')
    for item in onsets["candidates"]:
        anchor = _frac(item["anchorSourceSeconds"])
        if start <= anchor <= end:
            cx = x(anchor)
            pieces.append(f'<path d="M{cx:.2f},281 l7,10 l-7,10 l-7,-10 Z" '
                          'fill="#81e3b5" stroke="#13231f" stroke-width="2"/>')
    if not rhythm["intervals"]:
        pieces.append('<text x="209" y="197" class="no-audio">'
                      'Fewer than two candidate cuts</text>')

    audio_rows = []
    for region in regions[1:]:
        item = audio_by_region.get(region["id"])
        if item is None:
            before = after = "—"
            status = "No source audio" if av["status"] == "no-audio-stream" else "Unavailable"
        else:
            def fraction_text(side: dict[str, Any]) -> str:
                value = side["quietFrameFraction"]
                return "—" if value is None else f'{value*100:.0f}% ({side["frameCount"]} frames)'
            before = fraction_text(item["before"])
            after = fraction_text(item["after"])
            status = item["status"].replace("-", " ")
        audio_rows.append(
            '<tr><th scope="row">' + _h(region["id"]) + '</th><td>' +
            _h(_sec(_frac(region["startSeconds"]))) + '</td><td>' + _h(before) +
            '</td><td>' + _h(after) + '</td><td>' + _h(status) + '</td></tr>')
    onset_rows = []
    for item in onsets["candidates"]:
        anchor = _frac(item["anchorSourceSeconds"])
        window = item["supportWindow"]
        rise = item["measuredRmsRiseDb"]
        onset_rows.append(
            '<tr><th scope="row">' + _h(item["id"]) + '</th><td>' +
            _h(_sec(anchor)) + ' / PTS ' + _h(item["anchorSourcePts"]) +
            '</td><td>' + _h(_sec(_frac(window["startSeconds"]))) + '–' +
            _h(_sec(_frac(window["endSeconds"]))) + '</td><td>' +
            ('— (measurement floor)' if rise is None else _h(f"+{rise:.1f} dB")) +
            '</td><td>' + _h(item["signal"].replace("-", " ")) +
            '</td><td>' + ('Yes' if start <= anchor <= end else 'No') + '</td></tr>')
    rhythm_rows = [
        '<tr><th scope="row">' + _h(r["regionId"]) + '</th><td>' +
        _h(_sec(_frac(r["fromSeconds"]))) + ' to ' +
        _h(_sec(_frac(r["toSeconds"]))) + '</td><td>' +
        _h(_sec(_frac(r["durationSeconds"]))) + '</td><td>' +
        _h(r["changeVsPrevious"].replace("-", " ")) + '</td></tr>'
        for r in rhythm["intervals"]]
    motion_rows = []
    for region in regions:
        obs = region["observations"]
        motion, appearance = obs["motion"], obs["appearance"]
        displacement = (motion.get("meanGlobalImageDisplacementNormalized")
                        if isinstance(motion, dict) else None)
        luma = (appearance.get("meanDisplayLumaProxy")
                if isinstance(appearance, dict) else None)
        motion_rows.append('<tr><th scope="row">' + _h(region["id"]) +
                           '</th><td>' + _h(_sec(_frac(region["startSeconds"]))) +
                           '</td><td>' + ("—" if displacement is None else
                                          _h(f"{displacement:.4f}")) +
                           '</td><td>' + ("—" if luma is None else
                                          _h(f"{luma:.3f}")) + '</td></tr>')

    def rows_or_empty(rows: list[str], cols: int, message: str) -> str:
        return "".join(rows) if rows else f'<tr><td colspan="{cols}">{_h(message)}</td></tr>'

    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Kumiki reference evidence timeline</title><style>'
        ':root{color-scheme:dark;font-family:ui-sans-serif,system-ui,-apple-system,sans-serif;'
        '--bg:#0a111b;--surface:#111e2c;--text:#e8f2fc;--muted:#b2c1d0;'
        '--line:#31445c;--focus:#f1b970}*{box-sizing:border-box}'
        'body{margin:0;background:var(--bg);color:var(--text);font-size:15px;line-height:1.5}'
        'main{max-width:1200px;padding:clamp(18px,3vw,36px);margin:0 auto}'
        'h1{font-size:clamp(24px,3vw,36px);letter-spacing:-.03em;margin:0 0 8px}'
        'h2{font-size:19px;margin:35px 0 12px}p{color:var(--muted);margin:6px 0 18px}'
        '.eyebrow{color:#88bdd2;font-size:12px;letter-spacing:.12em;text-transform:uppercase}'
        '.lede{max-width:70ch}.meta{font-variant-numeric:tabular-nums;overflow-wrap:anywhere}'
        '.timeline{background:var(--surface);border:1px solid var(--line);'
        'border-radius:12px;padding:10px;overflow-x:auto;outline-offset:3px}'
        '.timeline:focus-visible,summary:focus-visible{outline:3px solid var(--focus)}'
        'svg{display:block;min-width:900px;width:100%;height:auto}'
        '.axis{font:12px ui-monospace,monospace;fill:#c1d0dc}'
        '.track-label{font:14px system-ui,sans-serif;fill:#d3e2ef}'
        '.region-label{font:11px ui-monospace,monospace;fill:#e0edf5}'
        '.interval-label{font:12px ui-monospace,monospace;fill:#f6d7b3}'
        '.no-audio{font:12px system-ui,sans-serif;fill:#9eafc1}'
        '.legend{display:flex;gap:18px;flex-wrap:wrap;margin:14px 2px 0;color:var(--muted);'
        'font-size:13px}.swatch{display:inline-block;width:10px;height:10px;'
        'border-radius:50%;margin-right:6px}.note{font-size:13px}'
        '.table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:10px}'
        'table{width:100%;border-collapse:collapse;min-width:600px;'
        'font-variant-numeric:tabular-nums}td,th{padding:10px 12px;text-align:left;'
        'border-bottom:1px solid #24364a}thead th{background:#16283a;color:#d9e9f8;'
        'font-size:12px}tbody th{font-weight:500;color:#dcebf8}tbody tr:last-child td,'
        'tbody tr:last-child th{border-bottom:0}'
        'details{border-top:1px solid var(--line);margin:34px 0 0;padding-top:16px}'
        'summary{cursor:pointer;color:#cce7f8;font-weight:600;padding:8px}'
        'code{overflow-wrap:anywhere}a{color:#a5d9ed}'
        '@media(prefers-reduced-motion:reduce){*,*:before,*:after{scroll-behavior:auto!important}}'
        '</style></head><body><main>'
        '<div class="eyebrow">Kumiki · measurement review</div>'
        '<h1>Reference timeline</h1><p class="lede">Video cut positions, apparent image motion, '
        'bounded pacing gaps, audio-level contrasts and possible audio attacks on a shared candidate '
        'presentation-time axis. They are observations, not reconstructed edit intent.</p>'
        '<p class="meta">' + _h(source_label) + ' · ' +
        _h(_sec(start)) + ' to ' + _h(_sec(end)) + ' observed · ' +
        str(len(regions)-1) + ' candidate cuts</p>'
        '<section aria-labelledby="plot-heading"><h2 id="plot-heading">Evidence at a glance</h2>'
        '<div class="timeline" role="region" tabindex="0" '
        'aria-label="Evidence timeline. Scroll horizontally to inspect all timestamps.">'
        '<svg viewBox="0 0 1200 332" role="img" '
        'aria-label="Visual alignment of video regions, motion magnitude, cut intervals, '
        'audio contrast and audio level attack markers; precise numbers are in the tables below">' +
        "".join(pieces) + '</svg></div>'
        '<div class="legend"><span><i class="swatch" style="background:#f1b970"></i>'
        'Candidate video cut</span><span><i class="swatch" style="background:#60bad2"></i>'
        'Apparent displacement per sampled pair</span><span><i class="swatch" '
        'style="background:#d0a9f5"></i>Quiet-level contrast candidate</span>'
        '<span><i class="swatch" style="background:#81e3b5"></i>Audio level attack candidate</span></div>'
        '<p class="note">The first and last bounded video regions are not complete '
        'shot-duration measurements. Audio/video clock alignment is provisional.</p></section>'
        '<section aria-labelledby="cut-heading"><h2 id="cut-heading">Audio near candidate cuts</h2>'
        '<div class="table-wrap"><table><thead><tr><th scope="col">Region after cut</th>'
        '<th scope="col">Source time</th><th scope="col">Quiet before</th>'
        '<th scope="col">Quiet after</th><th scope="col">Evidence status</th>'
        '</tr></thead><tbody>' + rows_or_empty(audio_rows, 5, "No candidate cuts in the scanned portion") +
        '</tbody></table></div><p class="note">Quiet fractions count decoded audio frames '
        'fully inside the comparison window, not verified sound events or synchronization.</p></section>'
        '<section aria-labelledby="onset-heading"><h2 id="onset-heading">Candidate audio level attacks</h2>'
        '<div class="table-wrap"><table><thead><tr><th scope="col">Candidate</th>'
        '<th scope="col">Audio PTS anchor</th><th scope="col">Two-frame support</th>'
        '<th scope="col">RMS rise</th><th scope="col">Signal</th>'
        '<th scope="col">In plotted video range</th></tr></thead><tbody>' +
        rows_or_empty(onset_rows, 6, "No candidate audio level attacks in the bounded scan") +
        '</tbody></table></div><p class="note">Each marker anchors the later audio frame, '
        'not the exact acoustic onset. Audio events outside the observed video region are '
        'listed here but not drawn. No speech, beat or SFX classification is performed.</p></section>'
        '<section aria-labelledby="rhythm-heading"><h2 id="rhythm-heading">Candidate cut intervals</h2>'
        '<div class="table-wrap"><table><thead><tr><th scope="col">Interior region</th>'
        '<th scope="col">Cut boundaries</th><th scope="col">Duration</th>'
        '<th scope="col">Relative to previous</th></tr></thead><tbody>' +
        rows_or_empty(rhythm_rows, 4, "At least two candidate cuts are needed for one measured gap") +
        '</tbody></table></div></section>'
        '<section aria-labelledby="motion-heading"><h2 id="motion-heading">Measured image characteristics</h2>'
        '<div class="table-wrap"><table><thead><tr><th scope="col">Candidate region</th>'
        '<th scope="col">Start time</th><th scope="col">Image shift (normalized/pair)</th>'
        '<th scope="col">Mean display luma proxy</th></tr></thead><tbody>' +
        rows_or_empty(motion_rows, 4, "No observed regions") +
        '</tbody></table></div></section>'
        '<details><summary>Measurement limits and provenance</summary><p>'
        'Source SHA-256: <code>' + _h(evidence["sourceSha256"]) + '</code>. '
        'Analysis SHA-256: <code>' + _h(evidence["analysisRunSha256"]) + '</code>. '
        'Video PTS and audio PTS are converted independently to rational seconds; '
        'the common source presentation clock has not been independently synchronized. '
        'Cuts can be false positives. Motion is 2D image displacement, not camera '
        'velocity. Luma is display-referred, not actual scene lighting. '
        'No semantic story, sound recognition, or artistic quality verdict was made.'
        '</p></details></main></body></html>\n')


def _verify(directory: Path, settings: dict[str, Any]) -> Path:
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("timeline review must be a regular directory")
    manifest = _json_file(directory / "timeline-review.json", limit=262_144)
    if (manifest.get("schemaVersion") != TIMELINE_REVIEW_VERSION or
            manifest.get("settings") != settings or
            manifest.get("qualityVerdict") != "not-performed"):
        raise ValueError("timeline review metadata differs from expected settings")
    records = manifest.get("files")
    expected = {"index.html", "shot-evidence.json", "edit-rhythm.json",
                "av-cut-evidence.json", "audio-onsets.json"}
    actual = [row for row in _file_records(directory) if row["path"] != "timeline-review.json"]
    if (not isinstance(records, list) or records != actual or
            {row["path"] for row in actual} != expected):
        raise ValueError("timeline review files were altered")
    for key, name in (("shotEvidenceSha256", "shot-evidence.json"),
                      ("editRhythmSha256", "edit-rhythm.json"),
                      ("avCutEvidenceSha256", "av-cut-evidence.json"),
                      ("audioOnsetsSha256", "audio-onsets.json")):
        if sha256_file(directory / name) != settings[key]:
            raise ValueError("timeline review evidence hash differs")
    return directory / "index.html"


def build_timeline_view(source: Path, analysis_run: Path, output: Path, *,
                        window_ms: int = 400, max_audio_frames: int = 4096,
                        onset_min_rise_db: float = 12.0,
                        onset_min_peak_dbfs: float = -40.0,
                        onset_cooldown_ms: int = 120,
                        ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe") -> Path:
    """Generate a checksum-verified static report from the same source bytes."""
    if type(window_ms) is not int or not 100 <= window_ms <= 2000:
        raise ValueError("timeline window_ms must be 100..2000")
    if type(max_audio_frames) is not int or not 1 <= max_audio_frames <= 10000:
        raise ValueError("timeline max_audio_frames must be 1..10000")
    if (type(onset_min_rise_db) not in (int, float) or
            not 1 <= onset_min_rise_db <= 60 or
            type(onset_min_peak_dbfs) not in (int, float) or
            not -100 <= onset_min_peak_dbfs <= 0 or
            type(onset_cooldown_ms) is not int or
            not 0 <= onset_cooldown_ms <= 2000):
        raise ValueError("timeline onset thresholds are outside supported bounds")
    resolved_out = output.resolve()
    if resolved_out.is_relative_to(analysis_run.parent.resolve()) or any(
            (parent / marker).exists() for parent in (resolved_out, *resolved_out.parents)
            for marker in ("study-manifest.json", "shot-gallery.json",
                           "technique-review.json")):
        raise ValueError("timeline output must be outside immutable analysis/review bundles")
    evidence = build_shot_evidence(analysis_run)
    rhythm = edit_rhythm_from_verified_shots(evidence)
    run = _json_file(analysis_run, limit=262_144)
    seconds = run["settings"]["seconds"]
    audio = analyze_audio_levels(
        source, seconds=seconds, max_frames=max_audio_frames, ffmpeg=ffmpeg,
        ffprobe=ffprobe, rights_status=run["settings"]["rightsStatus"])
    av = av_cut_evidence_from_levels(evidence, audio, seconds=seconds,
                                     window_ms=window_ms)
    onsets = audio_onsets_from_levels(
        audio, min_rise_db=onset_min_rise_db,
        min_peak_dbfs=onset_min_peak_dbfs, cooldown_ms=onset_cooldown_ms)
    _timing(evidence, rhythm, av, onsets)
    reports = {"shot-evidence.json": evidence, "edit-rhythm.json": rhythm,
               "av-cut-evidence.json": av, "audio-onsets.json": onsets}
    encoded = {name: json.dumps(report, indent=2, sort_keys=True,
                                ensure_ascii=False, allow_nan=False).encode("utf-8") + b"\n"
               for name, report in reports.items()}
    settings = {
        "sourceSha256": evidence["sourceSha256"],
        "analysisRunSha256": evidence["analysisRunSha256"],
        "styleRevision": STYLE_REVISION,
        "windowMs": window_ms, "maxAudioFrames": max_audio_frames,
        "onsetMinRiseDb": float(onset_min_rise_db),
        "onsetMinPeakDbFs": float(onset_min_peak_dbfs),
        "onsetCooldownMs": onset_cooldown_ms,
        "ffmpeg": ffmpeg, "ffprobe": ffprobe,
        "shotEvidenceSha256": hashlib.sha256(encoded["shot-evidence.json"]).hexdigest(),
        "editRhythmSha256": hashlib.sha256(encoded["edit-rhythm.json"]).hexdigest(),
        "avCutEvidenceSha256": hashlib.sha256(encoded["av-cut-evidence.json"]).hexdigest(),
        "audioOnsetsSha256": hashlib.sha256(encoded["audio-onsets.json"]).hexdigest(),
    }
    digest = hashlib.sha256(_serialize(settings)).hexdigest()[:16]
    destination = output / f'timeline-{settings["sourceSha256"][:12]}-{digest}'
    output.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        return _verify(destination, settings)
    with tempfile.TemporaryDirectory(prefix=".timeline-", dir=output) as name:
        staging = Path(name)
        for filename, report in reports.items():
            write_json_artifact(staging, filename, report)
        (staging / "index.html").write_text(
            render_timeline_html(evidence, rhythm, av, onsets,
                                 source_label=source.name),
            encoding="utf-8")
        write_json_artifact(staging, "timeline-review.json", {
            "schemaVersion": TIMELINE_REVIEW_VERSION, "settings": settings,
            "files": _file_records(staging), "qualityVerdict": "not-performed",
        })
        if destination.exists() or destination.is_symlink():
            return _verify(destination, settings)
        try:
            os.rename(staging, destination)
        except FileExistsError:
            return _verify(destination, settings)
    return destination / "index.html"
