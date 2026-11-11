"""Offline searchable What Ships catalog with optional provenance-checked analysis overlays.

No embedded media, external resources or private filesystem paths. Human review
is not inferred from successful model jobs or sampled RGB measurements.
"""
from __future__ import annotations

import csv
import io
import json
import math
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import sha256_file
from kumiki_reference_lab.catalog.video_sources import _from_whatships, _load_snapshot
from kumiki_reference_lab.catalog.whatships_media_bindings import _read_json, load_media_bindings
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.pipeline.whatships_local_worker import _read_previous_index
from kumiki_reference_lab.pipeline.whatships_visual_backfill import _read_previous_visual_index

SCHEMA_VERSION = "kumiki.whatships-browsable-video-data.v1"
_PROBE = "kumiki.source-pts-visual-probe.v1"


def _fraction(value: Any, name: str) -> float | None:
    if value is None:
        return None
    if type(value) not in (float, int) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("invalid measured visual fraction: "+name)
    return round(float(value), 6)


def _count(value: Any, name: str, maximum: int = 10000) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("invalid measured visual count: "+name)
    return value


def _project_numeric(artifacts: list[dict[str, Any]], expected_sha: str) -> dict[str, Any]:
    windows = []
    for item in artifacts:
        data = _read_json(Path(item["path"]))
        scan, summary = data.get("scan"), data.get("sampledWindowSummary")
        if (data.get("schemaVersion") != _PROBE or data.get("sourceSha256") != expected_sha
                or not isinstance(scan, dict) or not isinstance(summary, dict)
                or scan.get("startSeconds") != item["startSeconds"]
                or scan.get("sourceWindowEndSeconds") != item["endSeconds"]
                or scan.get("sampledSourcePtsCount") != item["sampledFrameCount"]
                or data.get("evidenceStatus") !=
                "original-source-pts-sampled-numeric-proxies-not-human-reviewed"):
            raise ValueError("numeric sample mismatches checked original video provenance")
        frame_count = _count(scan["sampledSourcePtsCount"], "frame count", 24)
        within = _count(summary.get("withinShotComparedPairs"), "within shot", 24)
        separated = _count(summary.get("cutSeparatedPairs"), "cut boundaries", 24)
        cuts = data.get("cutCandidatePts")
        if (within+separated != frame_count-1
                or not isinstance(cuts, list)
                or len(cuts) != _count(
                    summary.get("cutCandidateCountBetweenFirstAndLastSample"), "cuts")
                or cuts != sorted(set(cuts))
                or any(type(p) is not int for p in cuts)):
            raise ValueError("invalid measured cut timestamps or pair counts")
        inventory = scan.get("sourcePtsFramesSeenInInventory")
        if inventory is not None:
            inventory = _count(inventory, "source PTS frame inventory", 1000000)
            if inventory < frame_count:
                raise ValueError("source inventory cannot be smaller than decoded samples")
        windows.append({
            "startSeconds": item["startSeconds"], "endSeconds": item["endSeconds"],
            "sampledFrames": frame_count, "inventoriedFrames":inventory,
            "cutCandidates": len(cuts),
            "cutCandidatePts": cuts,
            "meanDisplayLuma": _fraction(
                summary.get("meanSampledDisplayLumaProxy"), "display luma"),
            "meanSaturation": _fraction(
                summary.get("meanSampledSaturationProxy"), "saturation"),
            "withinShotRgbChange": _fraction(
                summary.get("meanWithinShotDisplayRgbDelta"), "RGB change"),
            "comparedPairs": within, "cutSeparatedPairs": separated,
        })
    return {"windowsMeasured": len(windows), "windows": windows}


def build_whatships_browser(
    snapshot_path: Path, *, bindings_path: Path | None = None,
    analysis_path: Path | None = None, numeric_path: Path | None = None,
    repository_root: Path | None = None,
) -> dict[str, Any]:
    """Whitelisted public metadata + verified private artifacts, never private paths."""
    if (analysis_path is not None and bindings_path is None or
            numeric_path is not None and (bindings_path is None or analysis_path is None)):
        raise ValueError("analysis requires private bindings; numeric overlay also needs study index")
    paths = [p for p in (snapshot_path,bindings_path,analysis_path,numeric_path) if p is not None]
    signatures = [(p,file_signature(p)) for p in paths]
    snapshot = _load_snapshot(snapshot_path)
    catalog = _from_whatships(snapshot)
    media, studied, measured = {}, {}, {}
    if bindings_path is not None:
        media = {row["sourceId"]:row for row in load_media_bindings(
            bindings_path, snapshot, verify_files=False)["bindings"]}
    if analysis_path is not None:
        prior = _read_json(analysis_path)
        if not isinstance(prior, dict) or not isinstance(prior.get("configuration"), dict):
            raise ValueError("local study index lacks verified configuration")
        studied = {r["sourceId"]:r for r in _read_previous_index(
            analysis_path, config=prior["configuration"], bindings=media)}
    if numeric_path is not None:
        prior = _read_json(numeric_path)
        if not isinstance(prior, dict) or not isinstance(prior.get("configuration"), dict):
            raise ValueError("numeric study index lacks verified configuration")
        measured = {r["sourceId"]:r for r in _read_previous_visual_index(
            numeric_path, config=prior["configuration"], source_rows=media,
            original_studies={k:v for k,v in studied.items()
                              if v["status"] == "completed-unreviewed"})}
    committed = {}
    if repository_root is not None:
        # Runtime import avoids circular dependency: the analysis exporter
        # reuses the ordinary catalog dashboard without a committed overlay.
        from kumiki_reference_lab.catalog.whatships_analysis_store import validate_repository_analysis
        validate_repository_analysis(repository_root,snapshot_path)
        repo_index=_read_json(repository_root/"index.json")
        committed={
            row["sourceId"]:_read_json(repository_root/row["recordPath"])
            for row in repo_index["entries"]
        }
    entries, counts = [], Counter()
    for entry in catalog:
        sid = entry["id"]
        study, numeric = studied.get(sid), measured.get(sid)
        persisted = committed.get(sid)
        layers = persisted["evidence"] if persisted else {}
        spot = layers.get("browserSpotCheck")
        archived_numeric = layers.get("numericVisual")
        character_status = ("completed-unreviewed" if study and
                            study["status"] == "completed-unreviewed"
                            else "failed" if study else "not-run")
        visual_status = ("sampled-numeric-unreviewed" if numeric and
                         numeric["status"] == "measured-numeric-proxies-unreviewed"
                         else "failed" if numeric else "not-run")
        numeric_summary = (_project_numeric(
            numeric["probeArtifacts"],media[sid]["mediaSha256"])
            if visual_status == "sampled-numeric-unreviewed" else None)
        if archived_numeric is not None:
            if (numeric_summary is not None and media[sid]["mediaSha256"] !=
                    archived_numeric["sourceSha256"]):
                raise ValueError("private media and committed numeric evidence reference different source bytes")
            if numeric_summary is None:
                numeric_summary = {
                    "windowsMeasured":len(archived_numeric["windows"]),
                    "windows":[{
                        "startSeconds":w["startSeconds"],
                        "endSeconds":w["endSeconds"],
                        "sampledFrames":len(w["sampledFrames"]),
                        "inventoriedFrames":w["scan"].get("sourcePtsFramesSeenInInventory"),
                        "cutCandidates":len(w["cutCandidatePts"]),
                        "meanDisplayLuma":w["sampledWindowSummary"]["meanSampledDisplayLumaProxy"],
                        "meanSaturation":w["sampledWindowSummary"]["meanSampledSaturationProxy"],
                        "withinShotRgbChange":w["sampledWindowSummary"]["meanWithinShotDisplayRgbDelta"],
                    } for w in archived_numeric["windows"]],
                }
                visual_status = "sampled-numeric-unreviewed"
        if character_status == "not-run" and "characterStudyStatus" in layers:
            character_status = "completed-unreviewed"
        row = {
            "sourceId":sid, "title":entry["title"], "creator":entry["creator"],
            "category":entry["category"],"watchUrl":entry["watchUrl"],
            "originalUrl":entry["originalUrl"], "publishedOn":entry["publishedOn"],
            "views":entry["views"],"viewsCapturedAt":entry["viewsCapturedAt"],
            "durationSeconds":entry["durationSeconds"], "tags":entry["tags"][:30],
            "description":entry["description"][:1200],
            "metadataStatus":entry["evidenceStatus"],
            "mediaStatus":"operator-attested" if sid in media else "unbound",
            "characterStatus":character_status,"numericStatus":visual_status,
            "numeric":numeric_summary,"humanReviewed":False,
            "repositoryAnalysisStatus":(
                "tracked-partial-evidence" if persisted else "none"),
            "visualObservationTags":spot["visualTags"] if spot else [],
            "visibleMoments":spot["visibleMoments"] if spot else [],
            "techniqueHypotheses":spot["techniqueHypotheses"] if spot else [],
            "spotCheckCoverage":spot["coverage"] if spot else None,
            "browserObservedOn":spot["observedOn"] if spot else None,
        }
        entries.append(row)
        if persisted:
            counts["repositoryEvidenceRecords"] += 1
        if spot:
            counts["browserSpotCheckRecords"] += 1
        for k in ("metadataStatus","mediaStatus","characterStatus","numericStatus"):
            counts[k+":"+str(row[k])] += 1
    for p,s in signatures:
        require_unchanged(p,s)
    return {
        "schemaVersion":SCHEMA_VERSION,"retrievedOn":snapshot["retrievedOn"],
        "catalogSource":"https://whatships.com/search-index.json",
        "snapshotSha256":sha256_file(snapshot_path),
        "totalVideos":len(entries),
        "counts":dict(sorted(counts.items())),
        "categories":dict(sorted(Counter(x["category"] for x in entries).items())),
        "entries":entries,
        "limits":[
            "100% catalog presence does not mean all videos were observed or downloaded.",
            "Views and durations are source-attributed metadata, not source-frame measurements.",
            "Operator-declared local media identity and rights are not externally certified.",
            "AI characters and actor interactions are unreviewed; RGB/cut probes are sampled numeric proxies.",
            "No verified camera movement, lights, lens, production style or human review is claimed.",
            "No source videos, local paths, rights explanations or private error messages appear in this export.",
        ],
    }


def _spreadsheet_safe(value: Any) -> str:
    s = "" if value is None else str(value)
    return "'"+s if s.lstrip().startswith(("=","+","-","@")) or s.startswith(("\t","\n","\r")) else s


def _csv(data: dict[str, Any]) -> str:
    fields = ("sourceId","title","creator","category","watchUrl","originalUrl",
              "views","viewsCapturedAt","durationSeconds","publishedOn",
              "metadataStatus","mediaStatus","characterStatus","numericStatus",
              "measuredWindowCount","humanReviewed")
    file = io.StringIO(newline="")
    writer = csv.writer(file,lineterminator="\n")
    writer.writerow(fields)
    for row in data["entries"]:
        writer.writerow([
            _spreadsheet_safe(row.get(key) if key != "measuredWindowCount"
                              else row["numeric"]["windowsMeasured"] if row["numeric"] else None)
            for key in fields
        ])
    return file.getvalue()


_HTML = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'none'; connect-src 'none'; base-uri 'none'; form-action 'none'">
<title>What Ships | Video evidence explorer</title>
<style>
:root{color-scheme:light;font:14px/1.5 system-ui,sans-serif;background:#f6f8fb;color:#17233a}
body{margin:0 auto;max-width:1450px;padding:22px}h1{font-size:27px;margin:0}p{color:#4b5a76;max-width:1000px}
.stats{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0}.stat{background:white;border:1px solid #d3ddea;border-radius:9px;padding:12px 16px;flex:1;min-width:145px}
.stat b{display:block;font-size:24px}.stat span,.small{font-size:12px;color:#55637a}
.controls{background:white;padding:14px;border:1px solid #d3ddea;border-radius:8px;display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}
label{font-weight:600;display:flex;flex-direction:column;gap:5px;font-size:12px}select,input,button{font:inherit;padding:8px;border:1px solid #a5b4c9;border-radius:6px;background:#fff;color:#10223c}
input{min-width:260px}.wrap{overflow:auto;background:white;border:1px solid #d3ddea;border-radius:8px}
table{width:100%;border-collapse:collapse;min-width:920px}td,th{border-bottom:1px solid #e2e8f1;text-align:left;padding:10px;vertical-align:top}
th{background:#edf2f9;color:#44536c;font-size:12px}td{font-size:13px}a{color:#165bb0;text-decoration:none}a:hover{text-decoration:underline}
button{cursor:pointer}button:disabled{opacity:.45}.pager{display:flex;gap:10px;align-items:center;margin:14px 0}
dialog{border:1px solid #b2bdd1;border-radius:10px;max-width:min(880px,90vw);max-height:85vh;overflow:auto}
dialog::backdrop{background:#192f4d99}dl{display:grid;grid-template-columns:150px 1fr;gap:8px}dt{font-weight:700}dd{margin:0;overflow-wrap:anywhere}
.note{padding:12px 16px;background:#fff;border-left:3px solid #778cab}
</style></head><body>
<h1>What Ships / Video evidence explorer</h1>
<p>Search the full dated video catalog. Missing metadata is unknown, not zero. Character predictions and sampled pixel statistics are not human-reviewed cinematic observations.</p>
<section class="stats" id="stats"></section><div id="date" class="small"></div>
<section class="controls">
<label>Title, creator, description or tag<input type="search" id="search" placeholder="e.g. motion, paper cut"></label>
<label>Category<select id="category"><option value="">All categories</option></select></label>
<label>Metadata<select id="metadata"><option value="">Any</option><option value="detail-snapshot">Detailed</option><option value="index-only">Index only</option></select></label>
<label>Evidence<select id="evidence"><option value="">All</option><option value="bound">Authorized file linked</option><option value="observed">Saved visual observations</option><option value="characters">Unreviewed character study</option><option value="numeric">Numerical visual samples</option></select></label>
<label>Sort<select id="sort"><option value="title">Title</option><option value="views">Known views, descending</option><option value="recent">Known publication date, descending</option></select></label>
</section><p id="found" aria-live="polite"></p>
<div class="wrap"><table><thead><tr><th>Video</th><th>Creator</th><th>Category</th><th>Views</th><th>Duration</th><th>Evidence</th><th>Inspect</th></tr></thead><tbody id="rows"></tbody></table></div>
<div class="pager"><button id="prev">Previous</button><span id="page"></span><button id="next">Next</button></div>
<p class="note">This file works entirely offline with no network calls. Original watch-page links open only when clicked. Numeric color, brightness, and cut candidates are not camera/lens/lighting measurements. No media, thumbnails or private paths are embedded.</p>
<dialog id="modal"><button id="close">Close</button><h2 id="heading"></h2><dl id="facts"></dl><div id="measurements"></div></dialog>
<script type="application/json" id="dataset">__DATA__</script>
<script>
"use strict";
const data=JSON.parse(document.getElementById("dataset").textContent);
const byId=id=>document.getElementById(id);
function el(tag,value){const x=document.createElement(tag);if(value!==undefined)x.textContent=String(value);return x;}
function link(url,label){if(!url)return el("span","Unavailable");const x=el("a",label);x.href=url;x.target="_blank";x.rel="noopener noreferrer";return x;}
function count(x){return x===null?"unknown":Number(x).toLocaleString("en-US");}
function fmt(x){return x===null?"unknown":Number(x).toFixed(3);}
function stat(name,value){const x=el("div");x.className="stat";x.append(el("b",value),el("span",name));return x;}
function status(x){if(x.numericStatus==="sampled-numeric-unreviewed")return "Pixel measurements (unreviewed)";
if(x.characterStatus==="completed-unreviewed")return "Character model (unreviewed)";
if(x.visualObservationTags.length)return "Saved partial visual spotcheck";
if(x.mediaStatus==="operator-attested")return "Local source linked";return "Metadata only";}
let page=0,filtered=[];
function details(x){
byId("heading").textContent=x.title;const facts=byId("facts");facts.replaceChildren();
const pairs=[["ID",x.sourceId],["Creator",x.creator],["Category",x.category],
["Watch page",link(x.watchUrl,"What Ships")],["Original post",link(x.originalUrl,"X post")],
["Published",x.publishedOn||"Unknown"],["Duration",x.durationSeconds===null?"Unknown":x.durationSeconds+" seconds"],
["Historical views",count(x.views)+" captured "+(x.viewsCapturedAt||"unknown")],
["Metadata",x.metadataStatus],["Media",x.mediaStatus],["Character",x.characterStatus],
["Numeric image evidence",x.numericStatus],["Source-linked research",x.repositoryAnalysisStatus],
["Spot-check coverage",x.spotCheckCoverage||"Not observed"],
["Observed on",x.browserObservedOn||"Unknown"],["Human full-video reviewed","No"],
["Tags",(x.tags||[]).join(", ")||"Not captured"],["Description",x.description||"Not captured"]];
for(const [name,value]of pairs){facts.append(el("dt",name));const v=el("dd");v.append(value instanceof Node?value:document.createTextNode(String(value)));facts.append(v);}
const out=byId("measurements");out.replaceChildren();
if(x.visibleMoments.length){
 out.append(el("h3","Observed moments (selected samples only, no source timestamps)"));
 const ul=el("ul");for(const moment of x.visibleMoments)ul.append(el("li",moment));
 out.append(ul);
 out.append(el("h3","Technique tags"));
 out.append(el("p",(x.visualObservationTags||[]).join(", ")));
 if(x.techniqueHypotheses.length){
  out.append(el("h3","Unverified technique hypotheses"));
  const hy=el("ul");for(const text of x.techniqueHypotheses)hy.append(el("li",text));
  out.append(hy);
 }
}
if(x.numeric){out.append(el("h3","Sampled original-source video windows"));
const t=el("table"),head=el("tr");for(const name of ["Time (seconds)","Sampled frames","PTS inventory","Cut candidates","Display luma","Saturation","Within-shot RGB change"])head.append(el("th",name));t.append(head);
for(const w of x.numeric.windows){const row=el("tr");for(const val of [w.startSeconds+"–"+w.endSeconds,w.sampledFrames,
w.inventoriedFrames===null?"not recorded":w.inventoriedFrames,
w.cutCandidates,fmt(w.meanDisplayLuma),fmt(w.meanSaturation),fmt(w.withinShotRgbChange)])row.append(el("td",val));t.append(row);}out.append(t);
}else out.append(el("p","No original-frame numeric measurements were supplied for this video."));
byId("modal").showModal();}
function render(){
const search=byId("search").value.toLowerCase().trim(),cat=byId("category").value,meta=byId("metadata").value,ev=byId("evidence").value;
filtered=data.entries.filter(x=>(!cat||x.category===cat)&&(!meta||x.metadataStatus===meta)
&&(!search||[x.title,x.creator,x.category,x.description,x.sourceId,
    (x.tags||[]).join(" "),(x.visualObservationTags||[]).join(" "),
    (x.visibleMoments||[]).join(" "), (x.techniqueHypotheses||[]).join(" ")]
    .join(" ").toLowerCase().includes(search))
&&(!ev||(ev==="bound"&&x.mediaStatus==="operator-attested")
||(ev==="observed"&&x.repositoryAnalysisStatus==="tracked-partial-evidence")
||(ev==="characters"&&x.characterStatus==="completed-unreviewed")
||(ev==="numeric"&&x.numericStatus==="sampled-numeric-unreviewed")));
const normal=(a,b)=>a.title.localeCompare(b.title)||a.sourceId.localeCompare(b.sourceId);
if(byId("sort").value==="views")filtered.sort((a,b)=>(b.views??-1)-(a.views??-1)||normal(a,b));
else if(byId("sort").value==="recent")filtered.sort((a,b)=>(b.publishedOn||"").localeCompare(a.publishedOn||"")||normal(a,b));
else filtered.sort(normal);
page=Math.max(0,Math.min(page,Math.ceil(filtered.length/50)-1));
const tbody=byId("rows");tbody.replaceChildren();
for(const x of filtered.slice(page*50,(page+1)*50)){
const tr=el("tr"),name=el("td");name.append(link(x.watchUrl,x.title),el("div",x.sourceId));
const inspection=el("td"),button=el("button","Details");button.addEventListener("click",()=>details(x));inspection.append(button);
tr.append(name,el("td",x.creator),el("td",x.category),el("td",count(x.views)),
el("td",x.durationSeconds===null?"Unknown":x.durationSeconds+" sec"),el("td",status(x)),inspection);tbody.append(tr);}
byId("found").textContent=count(filtered.length)+" of "+count(data.totalVideos)+" catalog records";
byId("page").textContent="Page "+(page+1)+" / "+Math.max(1,Math.ceil(filtered.length/50));
byId("prev").disabled=page===0;byId("next").disabled=(page+1)*50>=filtered.length;
}
for(const cat of Object.keys(data.categories)){const opt=el("option",cat+" ("+data.categories[cat]+")");opt.value=cat;byId("category").append(opt);}
const c=data.counts;
byId("stats").append(stat("Indexed",count(data.totalVideos)),
stat("Detailed",count(c["metadataStatus:detail-snapshot"]||0)),
stat("Locally bound",count(c["mediaStatus:operator-attested"]||0)),
stat("Git-linked observations",count(c["repositoryEvidenceRecords"]||0)),
stat("Character studied",count(c["characterStatus:completed-unreviewed"]||0)),
stat("Numeric visual sampled",count(c["numericStatus:sampled-numeric-unreviewed"]||0)));
byId("date").textContent="Snapshot: "+data.retrievedOn+" | catalog SHA-256: "+data.snapshotSha256;
for(const name of ["search","category","metadata","evidence","sort"])byId(name).addEventListener("input",()=>{page=0;render();});
byId("prev").addEventListener("click",()=>{page--;render();});
byId("next").addEventListener("click",()=>{page++;render();});
byId("close").addEventListener("click",()=>byId("modal").close());render();
</script></body></html>
"""


def _html(data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=True, sort_keys=True,
                         separators=(",",":"), allow_nan=False)
    if len(payload.encode("utf-8")) > 8 * 1024 * 1024:
        raise ValueError("embedded offline catalog exceeds 8 MiB")
    payload = payload.replace("<","\\u003c").replace(">","\\u003e").replace("&","\\u0026")
    return _HTML.replace("__DATA__", payload)


def write_whatships_browser(
    snapshot_path: Path, out: Path, *, bindings_path: Path | None = None,
    analysis_path: Path | None = None, numeric_path: Path | None = None,
    repository_root: Path | None = None,
) -> Path:
    if out.exists() or out.is_symlink():
        raise ValueError("browser output must be a new nonexisting directory")
    data = build_whatships_browser(
        snapshot_path, bindings_path=bindings_path,
        analysis_path=analysis_path, numeric_path=numeric_path,
        repository_root=repository_root)
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".kumiki-whatships-browser-",dir=out.parent) as folder:
        staged=Path(folder)
        (staged/"whatships-videos.html").write_text(_html(data),encoding="utf-8")
        (staged/"whatships-videos.json").write_text(
            json.dumps(data,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")
        (staged/"whatships-videos.csv").write_text(_csv(data),encoding="utf-8")
        (staged/"README.txt").write_text(
            "Open whatships-videos.html directly in a browser. No server needed. "
            "This contains catalog metadata and only validated optional numeric "
            "source-frame proxies; it never contains original video files, "
            "local paths, private rights notes or unredacted errors.\n",encoding="utf-8")
        if out.exists() or out.is_symlink():
            raise ValueError("browser output was occupied before publication")
        os.replace(staged,out)
    return out/"whatships-videos.html"
