const pptxgen = require('pptxgenjs');
const path = require('path');
const pptx = new pptxgen();
pptx.layout='LAYOUT_WIDE';pptx.author='Oraik Systems LLP';pptx.subject='GeoLens local implementation and measured verification';pptx.title='GeoLens';pptx.company='Oraik Systems LLP';pptx.lang='en-IN';
pptx.theme={headFontFace:'Aptos Display',bodyFontFace:'Aptos',lang:'en-IN'};
const C={paper:'F7F6F0',ink:'142D38',teal:'006C78',muted:'566D72',line:'D8DED8'};
const out=__dirname;
function slide(n,title){const s=pptx.addSlide();s.background={color:C.paper};s.addText('geolens',{x:.5,y:.25,w:2,h:.3,fontSize:14,bold:true,color:C.ink,margin:0});s.addText(`${n} / 6`,{x:11.9,y:.25,w:.8,h:.3,fontSize:11,color:C.muted,margin:0});s.addText(title,{x:.5,y:.95,w:12.1,h:1,fontSize:32,color:C.ink,margin:0,breakLine:false});s.addText('LOCAL PROTOTYPE  |  23 OCT 2026',{x:.5,y:7.1,w:8,h:.2,fontSize:9,color:C.muted,margin:0});return s;}
function body(s,text,x=.6,y=2.25,w=11.8,size=22){s.addText(text,{x,y,w,h:4.5,fontSize:size,color:C.ink,margin:0,paraSpaceAfterPt:16,breakLine:false,fit:'shrink',valign:'top'});}
let s=slide(1,'A place and an hour, backed by evidence');
body(s,'Compare actual outdoor locations across complete activity windows.\n\nA synchronized map, venue × hour surface and inspectable scoring make the trade-offs visible.\n\nTen activities. English and Hindi. One local open-weights SLM.',.6,2.3,5.7,23);
s.addImage({path:path.join(out,'../output/playwright/chat-desktop.png'),x:6.7,y:2.25,w:6.05,h:3.78});
s.addText('Actual Lonavala query through the conversational interface.',{x:6.7,y:6.15,w:6,h:.4,fontSize:11,color:C.muted,margin:0});
s=slide(2,'What changes when you leave later?');
s.addImage({path:path.join(out,'../output/playwright/chat-followup.png'),x:.5,y:2.1,w:8,h:5});
body(s,'Lonavala follow-up\n\n07:00 → 09:00\n\nThe typed conversation retains location and hiking activity while recomputing the requested time.\n\nThe inspector exposes actual conditions and contribution changes.\n\nForecasts and heuristic points, not measured exposure or confidence.',8.8,2.2,4,19);
s.addNotes('Actual captured 23 October analysis for 24 October. OSM/OpenFreeMap attribution remains visible.');
s=slide(3,'Live retrieval, grounded computation');
body(s,'Question → local SLM interpretation\nGeocoding → OSM venues or attributed Geofabrik fallback\nHourly forecast + CAMS regional air quality\nGeometry, full-window restrictions and suitability scoring\nSLM option and evidence selection → predicate validation\nIndependent JSON API → synchronized website',.6,2.15,11.6,24);
s.addNotes('No stored recommendations. Extracts contain geography. Weather refreshes under source cache TTLs. Road and industry proximity are proxies; AQ is regional modeled US AQI.');
s=slide(4,'One small model, two substantive tasks');
body(s,'Qwen3.5-2B  |  Apache-2.0\n2,274,069,824 parameters in the full original release.\n\n1. Interpret activity, place, time, constraints and follow-up patches.\n2. Select eligible options and verifiable comparative evidence.\n\nPinned Q4_K_M runtime, 2 CPU threads, 2K context, thinking off.\nOriginal-format weights, tokenizer, config and licence staged locally.\nPublic Hugging Face publication and clean public load remain release gates.',.6,2.15,11.8,22);
s=slide(5,'Measured on the local machine');
body(s,'71 correctness tests pass across all ten activity profiles.\nTwo concurrent requests: 8.2–9.2 seconds, both HTTP 200.\nFive concurrent requests: 17.3–21.0 seconds, all HTTP 200.\nObserved model working set: about 1.5–2.0 GiB in these runs.\n\nRyzen AI 9 HX 370, Windows, 2 inference threads. These small samples do not establish p95 or production capacity. Linux container limits require deployment verification.',.6,2.15,11.8,23);
s=slide(6,'Release gates and scientific limits');
body(s,'Ready locally: API, website, model inference, genuine data fallback, tests and reproducibility files.\n\nStill required: chosen public GitHub/HF identities, successful public model load, authorized isolated deployment, externally verified API and judging-window uptime.\n\nNo live traffic, verified complete routes, guaranteed opening hours or medical clearance. Historical satellite imagery is context only.\n\nAI coding disclosure: OpenAI Codex. No sub-agents. No paid/private runtime inference or data API.',.6,2.15,11.8,22);
pptx.writeFile({fileName:path.join(out,'GeoLens.pptx')});
