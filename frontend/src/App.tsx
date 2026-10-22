import {useEffect,useMemo,useState,lazy,Suspense} from 'react';
import {ArrowUpRight,ArrowRight,ArrowLeft,Search,MapPin,Wind,CloudRain,Thermometer,Layers,ChevronDown,Check,LoaderCircle,Info,ExternalLink,Sun,Activity,Clock,ShieldCheck,X,Navigation} from 'lucide-react';
import type {Analysis,Option,Venue} from './types';
const MapScene=lazy(()=>import('./MapScene'));
const activities=[['running','Running'],['cycling','Cycling'],['golf','Golf'],['cricket','Cricket'],['football','Football'],['tennis','Tennis'],['hiking','Hiking'],['picnic','Picnic'],['outdoor_gathering','Gathering'],['outdoor_photography','Photography']];
const hh=(time:string)=>new Date(time).toLocaleTimeString('en-IN',{timeZone:'Asia/Kolkata',hour:'2-digit',minute:'2-digit',hour12:false});
const date=(time:string)=>new Date(time).toLocaleDateString('en-IN',{timeZone:'Asia/Kolkata',day:'numeric',month:'short'});
const number=(v:number|null|undefined,suffix='')=>v==null?'Unavailable':`${Math.round(v)}${suffix}`;
const label=(s:string)=>s.replaceAll('_',' ');

export default function App(){
  const [question,setQuestion]=useState('Where should I run tomorrow morning near Powai, Mumbai?');
  const [activity,setActivity]=useState('running'),[language,setLanguage]=useState('en'),[sensitive,setSensitive]=useState(false);
  const [analysis,setAnalysis]=useState<Analysis|null>(null),[jobId,setJobId]=useState<string|null>(null);
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[events,setEvents]=useState<{stage:string;message:string;at:string}[]>([]);
  const [selected,setSelected]=useState<string|null>(null),[hour,setHour]=useState(''),[inspector,setInspector]=useState(false),[showLayers,setShowLayers]=useState(false),[saved,setSaved]=useState(false),[snapshotAvailable,setSnapshotAvailable]=useState(false),[compareFrom,setCompareFrom]=useState<Option|null>(null),[ready,setReady]=useState<boolean|null>(null);
  useEffect(()=>{fetch('/readyz').then(r=>setReady(r.ok)).catch(()=>setReady(false));fetch('/v1/showcase').then(r=>setSnapshotAvailable(r.ok)).catch(()=>{});},[]);
  const venues=analysis?.venues||[],matrix=analysis?.matrix||[];
  const hours=useMemo(()=>[...new Set(matrix.map(o=>o.time))].sort(),[matrix]);
  const current=useMemo(()=>matrix.filter(o=>o.time===hour),[matrix,hour]);
  const ordered=useMemo(()=>[...current].sort((a,b)=>(a.eligibility==='eligible'?0:1)-(b.eligibility==='eligible'?0:1)||b.score_low-a.score_low),[current]);
  const venue=venues.find(v=>v.id===selected),option=current.find(o=>o.venue_id===selected)||ordered[0];
  const accept=(data:Analysis)=>{setAnalysis(data);const best=data.recommendations?.[0]||data.matrix?.[0];setHour(best?.time||'');setSelected(best?.venue_id||data.venues?.[0]?.id||null);};
  useEffect(()=>{
    if(!jobId)return;
    let alive=true;
    const timer=window.setInterval(async()=>{
      try{
        const response=await fetch(`/v1/analyses/${jobId}`),job=await response.json();
        if(!alive)return;
        if(!response.ok)throw new Error('Analysis could not be retrieved. Please retry.');
        setEvents(job.events||[]);
        if(job.status==='complete'){accept(job.result);setBusy(false);setJobId(null);setReady(true)}
        if(job.status==='error'){setError(job.error?.detail?.message||job.error?.detail?.code||'Analysis failed. Please retry.');setBusy(false);setJobId(null)}
      }catch(e){if(alive){setError(String(e));setBusy(false);setJobId(null)}}
    },750);
    return()=>{alive=false;window.clearInterval(timer)};
  },[jobId]);
  async function submit(text=question,chosenActivity=activity){
    if(busy)return;setBusy(true);setError('');setEvents([]);setSaved(false);setCompareFrom(null);
    try{
      const response=await fetch('/v1/analyses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:text,activity:chosenActivity,language,profile:{pollution_sensitive:sensitive},include:['evidence','hourly','geojson']})});
      const data=await response.json();if(!response.ok)throw new Error(data.detail?.message||JSON.stringify(data.detail));setJobId(data.analysis_id);
    }catch(e){setError(String(e));setBusy(false)}
  }
  async function rescore(value:boolean){
    setSensitive(value);if(!analysis||busy||saved)return;
    const id=analysis.request_id;
    try{const response=await fetch(`/v1/analyses/${id}/scenario`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pollution_sensitive:value})});if(!response.ok)throw new Error('Scenario expired. Run a fresh query.');accept(await response.json());}catch(e){setError(String(e))}
  }
  const changeActivity=(value:string)=>{setActivity(value);if(analysis)submit(question,value)};
  const delta=compareFrom&&option?option.score-compareFrom.score:null;
  const changes=compareFrom&&option?option.contributions.map((c,i)=>({factor:c.factor,delta:(c.points??-c.weight/2)-(compareFrom.contributions[i].points??-compareFrom.contributions[i].weight/2)})).filter(c=>Math.abs(c.delta)>.05).sort((a,b)=>Math.abs(b.delta)-Math.abs(a.delta)):[];
  return <main className="atlas">
    <header className="masthead">
      <a className="brand" href="/" aria-label="GeoLens home"><span className="brand-symbol"><Navigation size={20} strokeWidth={1.7}/></span>geo<span>lens</span><span className="brand-dot"/></a>
      
      <div className="header-right"><span className={`connection ${ready?'online':''}`}><i/>{ready?'Local model ready':ready===false?'Model not ready':'Checking model'}</span><button className="language" onClick={()=>setLanguage(language==='en'?'hi':'en')}>{language==='en'?'हिन्दी':'English'}</button><a href="/docs" target="_blank" rel="noreferrer" className="api-link">API <ArrowUpRight size={14}/></a></div>
    </header>
    <div className="workspace">
      <Suspense fallback={<div className="map map-placeholder">Loading geographic map…</div>}><MapScene venues={venues} selected={selected} options={current} onSelect={setSelected} layers={analysis?.layers} showLayers={showLayers}/></Suspense>
      <div className="map-context"><MapPin size={13}/>{analysis?.location?analysis.location.name.split(',').slice(0,2).join(','):'Mumbai, Maharashtra'}<span>INDIA</span></div>
      <aside className="query-sheet">
        
        <h1>Find your<br/><em>good hour.</em></h1>
        
        <form onSubmit={e=>{e.preventDefault();submit()}}>
          <label className="input-label" htmlFor="question">What are you heading out for?</label>
          <div className="query-input"><textarea id="question" value={question} onChange={e=>setQuestion(e.target.value)} rows={3} maxLength={2000}/><Search size={17}/></div>
          <div className="form-pair"><label>Activity<select value={activity} onChange={e=>changeActivity(e.target.value)}>{activities.map(([key,name])=><option key={key} value={key}>{name}</option>)}</select></label><label>Forecast area<span className="place-static"><MapPin size={14}/>From your question</span></label></div>
          <label className="sensitivity"><input type="checkbox" checked={sensitive} onChange={e=>rescore(e.target.checked)}/><span>I'm sensitive to air pollution</span><Info size={14}/></label>
          <button className="primary" disabled={busy||!question.trim()} type="submit">{busy?<><LoaderCircle size={17} className="spin"/>Analyzing real conditions</>:<>Find my place & time<ArrowRight size={18}/></>}</button>
        </form>
        {!analysis&&!busy&&<div className="explore"><span>Start somewhere familiar</span><div>{['Powai','Bandra','Lonavala'].map(place=><button key={place} onClick={()=>{const text=`Where should I ${activity==='running'?'run':activity.replaceAll('_',' ')} tomorrow morning near ${place}, Maharashtra?`;setQuestion(text);submit(text)}}>{place}<ArrowUpRight size={12}/></button>)}</div></div>}
        {snapshotAvailable&&!analysis&&<button className="snapshot-link" onClick={async()=>{const r=await fetch('/v1/showcase');accept(await r.json());setSaved(true)}}>Explore a captured real analysis<ArrowUpRight size={14}/></button>}
        {busy&&<div className="progress" role="status" aria-live="polite">{events.map((event,i)=><div key={i}>{i===events.length-1?<LoaderCircle size={13} className="spin"/>:<Check size={13}/>}<span>{event.message}</span></div>)}</div>}
        {error&&<div className="error" role="alert"><strong>Analysis couldn't finish.</strong><p>{error}</p><span>No invented answer has been substituted.</span></div>}
        {analysis&&<div className="result-summary"><div className="result-top"><ShieldCheck size={16}/>{saved?'Captured analysis · not live':analysis.status==='ok'?'Evidence-grounded result':'Analysis outcome'}<span>{date(analysis.generated_at)}</span></div><p>{analysis.answer}</p>{analysis.clarification?.choices?.map(choice=><button className="choice" key={choice} onClick={()=>{const text=`${question} in ${choice}`;setQuestion(text);submit(text)}}>{choice}<ArrowRight size={14}/></button>)}<button className="text-link" onClick={()=>setInspector(true)}>Inspect sources & assumptions<ArrowUpRight size={13}/></button></div>}
        <div className="sheet-footer"><span>Small model. Open data.</span><span>Built for the outdoors <Sun size={14}/></span></div>
      </aside>
      <div className="map-tools"><button className={showLayers?'active':''} onClick={()=>setShowLayers(!showLayers)}><Layers size={16}/>Geographic context</button><button onClick={()=>setInspector(true)}><Info size={16}/>Evidence</button></div>
      
      <section className={`decision-surface ${analysis?'populated':''}`} aria-label="Place by time decision surface">
        <div className="surface-top"><div><span className="matrix-icon"><Activity size={17}/></span><h2>Place × time</h2></div><div>{analysis&&<><span className="hour-stamp">{hour?`${date(hour)} · ${hh(hour)} IST`:''}</span><button className={compareFrom?'compare-button active':'compare-button'} disabled={!option} onClick={()=>setCompareFrom(compareFrom?null:option)}>{compareFrom?'Clear comparison':'Compare a moment'}</button></>}<span className="live-label">{saved?'SAVED SNAPSHOT':analysis?'RETRIEVED FORECAST':'READY TO EXPLORE'}</span></div></div>
        {!analysis?<div className="empty-matrix"><div><Clock size={24}/><p>Your next good hour is out there.</p><span>Ask above to compare actual locations across the forecast.<br/>No environmental data is shown until it has been retrieved.</span></div><div className="empty-axis" aria-hidden="true">{['05:00','07:00','09:00','11:00','13:00','15:00','17:00'].map(h=><span key={h}>{h}</span>)}</div></div>:<>
          <div className="matrix-scroll"><table className="matrix"><thead><tr><th scope="col">ACTUAL LOCATIONS <span>{venues.length}</span></th>{hours.map(h=><th scope="col" key={h} className={h===hour?'current':''}><button onClick={()=>setHour(h)}>{hh(h)}<small>{date(h)}</small></button></th>)}</tr></thead><tbody>{venues.map(v=><tr key={v.id} className={selected===v.id?'selected-row':''}><th scope="row"><button onClick={()=>setSelected(v.id)}><span className="venue-dot"/>{v.name}<small>{v.distance_km.toFixed(1)} km · straight-line</small></button></th>{hours.map(h=>{const o=matrix.find(x=>x.venue_id===v.id&&x.time===h);return <td key={h} className={h===hour?'current':''}><button disabled={!o} className={`score-cell ${o?.eligibility||'missing'} ${o?.id===option?.id?'chosen':''}`} style={{'--strength':o?o.score/100:0} as React.CSSProperties} onClick={()=>{setHour(h);setSelected(v.id)}} aria-label={`${v.name}, ${hh(h)}, ${o?.eligibility}, score range ${o?.score_low.toFixed(0)} to ${o?.score_high.toFixed(0)}`}>{o?o.eligibility==='eligible'?Math.round(o.score):o.eligibility==='avoid'?'Avoid':'—':'—'}</button></td>})}</tr>)}</tbody></table></div>
          <div className="surface-bottom"><span><i className="key-best"/>Higher suitability <i className="key-avoid"/>Avoid / restriction <i className="key-unknown"/>Insufficient data</span><span>Heuristic points, not confidence. Select any cell.</span></div>
        </>}
      </section>
      {analysis&&venue&&option&&<section className="venue-insight" aria-label="Selected venue and conditions"><div className="venue-heading"><span>{String(ordered.findIndex(o=>o.venue_id===venue.id)+1).padStart(2,'0')}</span><div><h2>{venue.name}</h2><p>{hh(option.time)}–{hh(option.end)} IST · {label(option.eligibility)}</p></div><button onClick={()=>setInspector(true)} aria-label="Inspect venue evidence"><ArrowUpRight size={19}/></button></div><div className="weather-row"><span><Thermometer size={15}/>{number(option.conditions.temperature,'°C')}</span><span><CloudRain size={15}/>{number(option.conditions.rain_probability,'%')}</span><span><Wind size={15}/>{number(option.conditions.wind_kmh,' km/h')}</span></div><div className="aq-line"><span>Regional modeled US AQI</span><strong>{number(option.conditions.us_aqi)}</strong><small>~45 km model</small></div>{compareFrom&&<div className="counterfactual"><strong>{delta!=null&&delta>0?'+':''}{delta?.toFixed(1)} points <span>vs {hh(compareFrom.time)}</span></strong>{changes.length?changes.slice(0,3).map(c=><p key={c.factor}>{label(c.factor)}<span>{c.delta>0?'+':''}{c.delta.toFixed(1)}</span></p>):<p>The calculated score is unchanged.</p>}<p className="eligibility-change">{label(compareFrom.eligibility)} → {label(option.eligibility)}</p></div>}</section>}
      {inspector&&<aside className="evidence-panel"><div className="evidence-title"><h2>Behind the decision</h2><button onClick={()=>setInspector(false)} aria-label="Close evidence"><X size={20}/></button></div>{!analysis?<p>Run an analysis to inspect real sources, measurements and scoring assumptions.</p>:<><p className="captured">{saved?'Saved analysis captured':'Data retrieved'} {new Date(analysis.generated_at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})} IST</p>{option&&<><h3>Suitability decomposition</h3><p className="score-range">{option.score_low.toFixed(0)}–{option.score_high.toFixed(0)}<span>/100 · heuristic range</span></p>{option.contributions.map(c=><div className="factor" key={c.factor}><span>{label(c.factor)}</span><strong>{c.points==null?'Unknown':c.points.toFixed(1)}</strong></div>)}<h3>Restrictions & gaps</h3>{[...option.warning_codes,...option.limitations].map(l=><p className="limitation" key={l}>{label(l)}</p>)}</>}<h3>Source ledger</h3>{analysis.evidence.map((e,i)=><div className="source" key={i}><strong>{String(e.id||'Source')}<span>{String(e.kind||'')}</span></strong>{Boolean(e.url)&&<a href={String(e.url)} target="_blank" rel="noreferrer">{new URL(String(e.url)).hostname}<ExternalLink size={12}/></a>}<small>{e.retrieved_at?new Date(String(e.retrieved_at)).toLocaleString('en-IN'):String(e.reason||e.status||'Not available')}{e.cache?' · cached':''}</small></div>)}<h3>What this cannot establish</h3>{analysis.limitations.map(l=><p className="limitation" key={l}>{l}</p>)}<h3>Assumptions</h3>{analysis.assumptions.map(l=><p className="limitation" key={l}>{l}</p>)}<h3>Before you go</h3>{analysis.precautions.map(l=><p className="limitation" key={l}>{l}</p>)}</>}</aside>}
    </div>
    <footer className="page-footer"><span>GEOLENS / GEOAI 2026</span><span>© OpenStreetMap contributors</span></footer>
  </main>;
}

