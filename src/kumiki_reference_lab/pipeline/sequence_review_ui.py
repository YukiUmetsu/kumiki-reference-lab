"""Static, offline-only UI assets for visual-change human annotation.

No remote scripts, network calls, cookies, databases or image embedding.
The HTML builder inserts source-bound label JSON and actual verified frame links.
"""

STYLES = r"""
:root{color-scheme:dark;font-family:system-ui,sans-serif;color:#edf3fc;background:#0b111a}
*{box-sizing:border-box}body{margin:0 auto;padding:1.5rem;max-width:1280px;line-height:1.5}
h1{font-size:1.7rem}.subtle{color:#b9c9d8}
.toolbar{position:sticky;top:0;z-index:3;background:#18263b;padding:1rem;display:flex;
 gap:.75rem;flex-wrap:wrap;align-items:center;border:1px solid #4a6082;border-radius:.6rem}
button,input,select{font:inherit;border-radius:.35rem;padding:.55rem;background:#293d58;
 color:#fff;border:1px solid #7990aa}
button{cursor:pointer}button:disabled{opacity:.5;cursor:not-allowed}
input[type=file]{font-size:.83rem;max-width:220px}
.sequence{background:#121d2c;border:1px solid #394b66;padding:1rem;
 margin:1.2rem 0;border-radius:.6rem}
.sequence header{display:flex;align-items:baseline;justify-content:space-between;gap:1rem}
.sequence h2{font-size:1.15rem;margin:0}.subjects{color:#b9c9d8}
.frames{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.7rem}
figure{margin:0;min-width:0}.frame{position:relative;aspect-ratio:var(--aspect);
 background:#070b11;overflow:hidden}
.frame img{width:100%;height:100%;display:block;object-fit:fill}
.roi{position:absolute;outline:2px solid #ff5b64;pointer-events:none}
.roi-B{outline-color:#35e0f1}
.roi-tag{position:absolute;left:0;top:0;background:#ff5b64;color:#111;
 font:bold .8rem system-ui;padding:0 .25rem}
.roi-B .roi-tag{background:#35e0f1}
figcaption{font-size:.78rem;color:#c1d0df;margin-top:.3rem}
.phases{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));
 gap:1rem;margin-top:1rem}
.review-phase{display:grid;gap:.3rem;font-size:.88rem}
.review-phase select{width:100%;min-width:0}
.note{border-left:3px solid #9badc4;padding:.5rem 1rem;color:#ced9e4}
#feedback{min-height:1.4em;color:#d4e6fb}
@media(max-width:680px){.toolbar{position:static}.frames{grid-template-columns:1fr 1fr}
.phases{grid-template-columns:1fr}}
"""

SCRIPT = r"""
"use strict";
// This page is a local file. No network calls, remote scripts, or hidden
// storage. The reviewer explicitly chooses labels and exports local JSON.
const baseline = JSON.parse(document.getElementById("pending-template").textContent);
const selectors = [...document.querySelectorAll(".phase-select")];
const categories = new Set([...selectors[0].options].map(o=>o.value).filter(Boolean));
const reviewer = document.getElementById("reviewer");
const complete = document.getElementById("complete");
const feedback = document.getElementById("feedback");
const importInput = document.getElementById("import");
function refresh(){
  const count = selectors.filter(s=>categories.has(s.value)).length;
  document.getElementById("progress").textContent =
    String(count)+"/"+String(selectors.length)+" phases labeled";
  const name=reviewer.value.trim();
  complete.disabled = count!==selectors.length || name.length<2 ||
    name.length>100 || name==="unassigned";
}
function exportDocument(approved){
  const result=JSON.parse(JSON.stringify(baseline));
  const name=reviewer.value.trim();
  result.reviewer={kind:"human",id:name||"unassigned"};
  for(const selector of selectors){
    const index=Number(selector.dataset.sequence);
    const phase=Number(selector.dataset.phase);
    result.sequences[index].phases[phase].humanCategory =
      categories.has(selector.value)?selector.value:null;
  }
  if(approved){
    if(complete.disabled)throw new Error("Label each phase and enter your reviewer ID.");
    result.coverageDeclaration="all-listed-source-frame-phases-human-reviewed";
  }else result.coverageDeclaration="pending-review";
  return result;
}
function download(approved){
  try{
    const payload=JSON.stringify(exportDocument(approved),null,2)+"\n";
    const url=URL.createObjectURL(new Blob([payload],{type:"application/json"}));
    const link=document.createElement("a");
    link.href=url;
    link.download=approved?"human-phase-labels.reviewed.json":"human-phase-labels.draft.json";
    document.body.appendChild(link);link.click();link.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
    feedback.textContent=approved?
      "Exported declared human labels. Evaluate separately to validate source evidence.":
      "Saved a pending draft, which cannot yet be benchmarked.";
  }catch(error){feedback.textContent=String(error);}
}
document.getElementById("draft").addEventListener("click",()=>download(false));
complete.addEventListener("click",()=>download(true));
for(const selector of selectors)selector.addEventListener("change",refresh);
reviewer.addEventListener("input",refresh);
importInput.addEventListener("change",async(event)=>{
  const file=event.target.files?.[0];
  if(!file)return;
  try{
    if(file.size>1500000)throw new Error("Draft JSON exceeds size budget.");
    const doc=JSON.parse(await file.text());
    for(const key of ["schemaVersion","sourceSha256",
        "insightsFileSha256","modelTagObserved"]){
      if(doc[key]!==baseline[key])throw new Error("Source or model provenance changed.");
    }
    if(!Array.isArray(doc.sequences)||
       doc.sequences.length!==baseline.sequences.length)
      throw new Error("Draft sequence count changed.");
    const imported=[];
    for(let i=0;i<doc.sequences.length;i++){
      const a=doc.sequences[i],b=baseline.sequences[i];
      for(const key of ["sequenceId","shotId","subjectIds",
          "frameIndices","sourceDecodedSeconds"]){
        if(JSON.stringify(a[key])!==JSON.stringify(b[key]))
          throw new Error("Draft sequence identity or source anchors changed.");
      }
      if(!Array.isArray(a.phases)||a.phases.length!==2)
        throw new Error("Draft phase count changed.");
      for(let j=0;j<2;j++){
        const p=a.phases[j],q=b.phases[j];
        if(p.phase!==q.phase || !(p.humanCategory===null ||
          categories.has(p.humanCategory)))
          throw new Error("Invalid draft phase category.");
        imported.push(p.humanCategory||"");
      }
    }
    if(doc.reviewer?.kind!=="human" ||
       typeof doc.reviewer.id!=="string" || doc.reviewer.id.length>100)
      throw new Error("Draft reviewer metadata invalid.");
    // Finish validation before changing any controls. Import never approves.
    selectors.forEach((node,i)=>{node.value=imported[i];});
    reviewer.value=doc.reviewer.id==="unassigned"?"":doc.reviewer.id;
    refresh();
    feedback.textContent="Draft restored. Inspect each label before human approval.";
  }catch(error){feedback.textContent="Import rejected: "+String(error);}
  finally{event.target.value="";}
});
refresh();
"""
