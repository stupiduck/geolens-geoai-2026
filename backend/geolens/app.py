"""Browser-independent HTTP API and immutable analysis snapshots."""
import asyncio
import json
import logging
import re
import time
import uuid
from copy import deepcopy
from . import conversation
from .narrative import render as render_answer
import httpx
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .config import settings
from .engine import ACTIVITIES, RULE_VERSION, DURATIONS, IST, evaluate, compare, resolve_time
from .model import model
from .sources import Sources

logger = logging.getLogger("geolens")
app = FastAPI(title="GeoLens", version="0.1.0", description="Evidence-grounded place × time outdoor intelligence. Scores are heuristics, not safety guarantees.")
app.add_middleware(CORSMiddleware, allow_origins=[settings.public_origin], allow_methods=["GET","POST"], allow_headers=["Content-Type"])
sources = Sources()
jobs = {}
inflight = 0


class Location(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str | None = Field(None,max_length=300)
    latitude: float | None = Field(None,ge=-90,le=90)
    longitude: float | None = Field(None,ge=-180,le=180)
    id: str | None = Field(None,max_length=120)
    name: str | None = Field(None,max_length=500)

    @model_validator(mode="after")
    def paired(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Both coordinates are required")
        if self.text and self.latitude is not None:
            raise ValueError("Supply a place name or coordinates, not both")
        return self


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pollution_sensitive: bool = False
    child_present: bool = False
    older_adult: bool = False
    pregnancy: bool = False


class Constraints(BaseModel):
    model_config = ConfigDict(extra="forbid")
    avoid_steep_terrain: bool = False
    max_grade_percent: float | None = Field(None,ge=0,le=50)
    daylight_only: bool = False
    max_travel_minutes: int | None = Field(None,ge=1,le=180)


class TimeRange(BaseModel):
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def valid_range(self):
        if self.start.tzinfo is None or self.end.tzinfo is None or self.end<=self.start or self.end-self.start>timedelta(days=7):
            raise ValueError("Supply an increasing, timezone-aware range of at most seven days")
        return self


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1,max_length=2000)
    conversation_id: str | None = Field(None,min_length=16,max_length=64)
    language: Literal["auto","en","hi"] = "auto"
    location: Location | None = None
    activity: Literal[tuple(ACTIVITIES)] | None = None
    radius_km: float | None = Field(None,ge=.5,le=50)
    duration_minutes: int | None = Field(None,ge=15,le=360)
    time_range: TimeRange | None = None
    profile: Profile | None = None
    constraints: Constraints | None = None
    include: list[Literal["evidence","hourly","geojson"]] = ["evidence"]


def timestamp():
    return datetime.now(IST).isoformat()


def base_result(identifier):
    return {"request_id":identifier,"generated_at":timestamp(),"timezone":"Asia/Kolkata","recommendations":[],"alternatives":[],"avoid_windows":[],"precautions":[],"evidence":[],"limitations":[],"assumptions":[],"data_status":{},"model":{"id":settings.model_id,"revision":settings.model_revision,"self_hosted":True,"thinking":False},"rule_version":RULE_VERSION}


def rank(matrix):
    return sorted((o for o in matrix if o["eligibility"]=="eligible"), key=lambda o:(-o["score_low"],-o["score"],o["venue_id"],o["time"]))


async def run_query(query, identifier, emit):
    started = time.perf_counter()
    result = base_result(identifier)
    await emit("model", "Interpreting activity and constraints")
    previous=conversation.sessions.get(query.conversation_id,{}).get('result')
    if previous:
        patch,it=await model.followup(query.question,conversation.context(previous))
        intent=conversation.merge(previous,patch)
    else:
        intent,it=await model.interpret(query.question)
    context_range=intent.pop('_time_range',None)
    location_changed=intent.pop('_location_changed',False)
    language = intent["language"] if query.language=="auto" else query.language
    activity = query.activity or intent["activity"]
    intent.update(activity=activity,language=language)
    # Preserve explicit API overrides even when a turn needs clarification.
    retained=intent.setdefault('constraints',{})
    if query.profile:
        for key,value in query.profile.model_dump(exclude_unset=True).items():
            intent[key]=bool(intent.get(key)) or value
            retained[key]=intent[key]
    if query.constraints:retained.update(query.constraints.model_dump(exclude_unset=True))
    if query.radius_km is not None:retained['radius_km']=query.radius_km
    if query.duration_minutes is not None:retained['duration_minutes']=query.duration_minutes
    if query.time_range:retained.update(start=query.time_range.start.isoformat(),end=query.time_range.end.isoformat())
    result["normalized_intent"] = intent
    result["timing_ms"] = {"intent":it}
    result['input']={'question':query.question,'language':language,'selected_location':query.location.model_dump(exclude_none=True) if query.location else None}
    if intent.get("commute"):
        return {**result,"status":"needs_clarification","answer":"कृपया यात्रा का शुरुआती स्थान और गंतव्य बताएं। इस संस्करण में पूरे यात्रा मार्ग का विश्लेषण उपलब्ध नहीं है।" if language=='hi' else "Please supply your starting area and destination for commute planning. Route-level commute analysis is not yet available in this build.","clarification":{"fields":["origin","destination"],"reason":"route_analysis_unavailable"}}
    if activity not in ACTIVITIES:
        return {**result,"status":"out_of_scope","answer":"Please choose an outdoor activity: running, cycling, golf, cricket, football, tennis, hiking, picnic, outdoor gathering or photography."}
    prior_location=previous.get('location') if previous else None
    if query.location:
        location=query.location
    elif prior_location and not location_changed:
        location=Location(latitude=prior_location['latitude'],longitude=prior_location['longitude'],name=prior_location['name'],id=prior_location.get('id'))
    else:
        location=Location(text=intent.get('location'))
    if location.latitude is None and not location.text:
        return {**result,"status":"needs_clarification","answer":"कृपया अपना इलाका या शहर बताएं।" if language=="hi" else "Which area or city should I search near?","clarification":{"fields":["location"]}}
    now = datetime.now(IST)
    start,end = resolve_time(intent.get("time_expression") or query.question,now)
    if context_range:start,end=context_range
    if query.time_range:
        start,end = query.time_range.start.astimezone(IST),query.time_range.end.astimezone(IST)
    if end<=now or start>now+timedelta(days=7):
        return {**result,"status":"needs_clarification","answer":"Please choose a future time within the next seven days."}
    radius = query.radius_km or intent.get("radius_km") or intent.get("constraints",{}).get("radius_km") or 5
    duration = query.duration_minutes or intent.get("duration_minutes") or intent.get("constraints",{}).get("duration_minutes") or DURATIONS.get(activity,60)
    if not .5<=radius<=50 or not 15<=duration<=360:
        return {**result,"status":"needs_clarification","answer":"Please use a radius between 0.5–50 km and duration between 15–360 minutes."}
    constraints = {k:bool(intent.get(k)) for k in ("pollution_sensitive","child_present","older_adult","pregnancy","avoid_steep_terrain")}
    constraints.update({k:v for k,v in intent.get("constraints",{}).items() if k not in conversation.FLAGS})
    constraints["prefer_greener"]=bool(intent.get("prefer_greener",constraints.get("prefer_greener",False)))
    if query.profile:
        for key,value in query.profile.model_dump(exclude_unset=True).items():
            constraints[key]=bool(constraints.get(key)) or value
    if query.constraints:
        constraints.update(query.constraints.model_dump(exclude_unset=True))
    constraints.update({"radius_km":radius,"duration_minutes":duration,"start":start.isoformat(),"end":end.isoformat()})
    if activity=='outdoor_photography':
        constraints['photography_goal']='sunset' if re.search('sunset|सूर्यास्त',query.question,re.I) else constraints.get('photography_goal','general')
    result["assumptions"] = [f"Search radius: {radius:g} km straight-line; activity duration: {duration} minutes.",f"Evaluated local start times: {start.isoformat()} to {end.isoformat()}."]
    result["normalized_intent"].update({"activity":activity,"constraints":constraints,"language":language})
    await emit("location", "Resolving the search area")
    if location.latitude is not None:
        lat,lon = location.latitude,location.longitude
        # Coordinates are explicit user input; never silently substitute a city.
        if not (6<=lat<=38 and 68<=lon<=98):
            return {**result,"status":"out_of_scope","answer":"This prototype supports Indian search areas."}
        name = location.name or f"{lat:.4f}, {lon:.4f}"
        result['evidence'].append({'id':'location','kind':'user_selected_coordinate' if location.id else 'user_provided_coordinate','location_id':location.id,'latitude':lat,'longitude':lon,'retrieved_at':timestamp()})
    else:
        places,meta = await sources.geocode(location.text)
        result["evidence"].append({"id":"location","kind":"mapped_feature",**meta})
        if not places:
            return {**result,"status":"needs_clarification","answer":"I could not resolve that Indian location. Add the city/state or choose coordinates."}
        # Same named area in different states/cities needs a deliberate choice.
        if len(places)>1 and places[0].get("address",{}).get("state")!=places[1].get("address",{}).get("state"):
            return {**result,"status":"needs_clarification","answer":"आप किस स्थान की बात कर रहे हैं?" if language=='hi' else "Which location did you mean?","clarification":{"fields":["location"],"choices":[{'id':f"{p.get('osm_type','place')}/{p.get('osm_id',p.get('place_id'))}",'name':p['display_name'],'latitude':float(p['lat']),'longitude':float(p['lon'])} for p in places]}}
        lat,lon,name = float(places[0]["lat"]),float(places[0]["lon"]),places[0]["display_name"]
    result["location"] = {"latitude":lat,"longitude":lon,"name":name,"radius_km":radius,"id":location.id}
    if previous:result["context_used"]={"previous_request_id":previous["request_id"],"area_retained":not location_changed,"language":language}
    await emit("venues", "Finding actual mapped activity locations")
    venues,meta = await sources.venues(lat,lon,radius,activity)
    result["evidence"].append({"id":"venues","kind":"mapped_feature",**meta})
    if not venues:
        return {**result,"status":"insufficient_data","answer":"No matching mapped venues were found in this radius. Try a wider radius or another activity; I will not invent a location."}
    await emit("forecasts", f"Retrieving hourly conditions for {len(venues)} locations")
    forecasts,features = await asyncio.gather(sources.forecasts(venues),sources.features(lat,lon,radius,venues))
    if activity in {"hiking","cycling"}:
        terrain=await sources.terrain(venues)
        result["evidence"].append({"id":"terrain",**terrain})
    result["evidence"].extend({"id":key,**meta} for key,meta in forecasts.items())
    result["evidence"].append({"id":"geography","kind":"spatial_proxy",**{k:v for k,v in features.items() if k!="geojson"}})
    result["data_status"] = {"weather":"available","air_quality":forecasts["air_quality"].get("status","available"),"geography":features["status"],"live_traffic_available":False,"venue_source":meta.get("mode","overpass")}
    await emit("scoring", "Comparing complete venue–time windows")
    matrix = evaluate(venues,[],activity,constraints)
    ordered = rank(matrix)
    result.update({"venues":venues,"matrix":matrix,"evaluated_venues":len(venues),"evaluated_windows":len(matrix),"layers":features.get("geojson")})
    result["limitations"] = ["US AQI is a regional CAMS Global model (~45 km, native 3-hourly), not a park sensor or Indian CPCB AQI.","Road/industry/green factors are mapped proxies, not live traffic or pollution concentrations.","Venue access, opening, booking and current surface conditions require confirmation.","Suitability scores are policy heuristics, not probabilities or medical clearance."]
    if features["status"]!="available":
        result["limitations"].append("Geographic feature measurements unavailable; score ranges include missing factors.")
    result["avoid_windows"] = [o for o in matrix if o["eligibility"]=="avoid"][:24]
    if not ordered:
        result.update({"status":"no_suitable_option","answer":"इस समय के लिए पर्याप्त प्रमाण वाली उपयुक्त जगह नहीं मिली।" if language=="hi" else "No sufficiently supported suitable option was found in this time window. Review the avoidance reasons or choose another time."})
    else:
        shortlist = []
        for option in ordered:
            if option["venue_id"] not in {o["venue_id"] for o in shortlist}:
                shortlist.append(option)
            if len(shortlist)==3:
                break
        if len(shortlist)==1 and len(ordered)>1:
            shortlist.append(ordered[1])
        await emit("reasoning", "Comparing evidence with the local small model")
        reasoning,rt = await model.reason(shortlist,constraints)
        result["timing_ms"]["comparison"] = rt
        preferred = next(o for o in shortlist if o["id"]==reasoning["preferred_id"])
        best = next(v for v in venues if v["id"]==preferred["venue_id"])
        time_label = datetime.fromisoformat(preferred["time"]).strftime("%d %b, %H:%M")
        near_tie = len(shortlist)>1 and preferred["score_low"]<=max(o["score_high"] for o in shortlist if o["id"]!=preferred["id"])
        result.update({"status":"ok","recommendations":[preferred],"alternatives":[o for o in shortlist if o["id"]!=preferred["id"]],"reasoning":reasoning,"ranking_stability":"conditional_near_tie" if near_tie else "separated_by_score_bounds",
            "answer":f"{best['name']} | {time_label} IST. उपयुक्तता {preferred['score_low']:.0f}–{preferred['score_high']:.0f}/100। प्रवेश और समय की पुष्टि करें।" if language=="hi" else f"{best['name']} at {time_label} IST: heuristic suitability {preferred['score_low']:.0f}–{preferred['score_high']:.0f}/100. Confirm access and opening hours."})
        if near_tie:
            result["answer"] += " स्कोर की सीमाएं मिलती हैं, इसलिए अन्य विकल्प भी उचित हो सकते हैं।" if language=='hi' else " Close alternatives remain plausible because score ranges overlap."
        names={v['id']:v['name'] for v in venues}
        options_by_id={o['id']:o for o in shortlist}
        phrases={'more_mapped_green':('has more mapped woodland nearby than','के पास इस विकल्प से अधिक मानचित्रित वन क्षेत्र है:'),"higher_score":("has a higher heuristic suitability score than","की गणना की गई उपयुक्तता इससे बेहतर है:"),"cooler_than":("has a lower start-hour temperature than","के शुरू के घंटे का तापमान इससे कम है:"),"less_rain_than":("has a lower start-hour rain probability than","के शुरू के घंटे में बारिश की संभावना इससे कम है:"),"cleaner_regional_air":("has lower modeled regional US AQI than","का क्षेत्रीय मॉडल वाला US AQI इससे कम है:"),"regional_aq_shared":("shares the same modeled regional US AQI with","और इस विकल्प का क्षेत्रीय मॉडल वाला US AQI समान है:"),'lower_thermal_penalty':('has a more comfortable temperature forecast than','में तापमान की असुविधा इससे कम है:'),'lower_road_proxy':('has less nearby mapped road/industry exposure than','का सड़क/उद्योग निकटता संकेत इससे कम है:'),'shorter_trip':('is closer to your search area than','की दूरी की असुविधा इससे कम है:')}
        result['explanations']=[]
        for claim in reasoning['claims']:
            a,b=options_by_id[claim['subject']],options_by_id[claim['object']]
            text=f"{names[a['venue_id']]} ({datetime.fromisoformat(a['time']).strftime('%H:%M')}) {phrases[claim['predicate']][1 if language=='hi' else 0]} {names[b['venue_id']]} ({datetime.fromisoformat(b['time']).strftime('%H:%M')})."
            references={'more_mapped_green':['geography'],'shorter_trip':['venues','location'],'lower_road_proxy':['venues','geography','weather'],'lower_thermal_penalty':['weather'],'cooler_than':['weather'],'less_rain_than':['weather'],'cleaner_regional_air':['air_quality'],'regional_aq_shared':['air_quality'],'higher_score':['venues','weather','air_quality','geography']}
            result['explanations'].append({'text':text,'predicate':claim['predicate'],'evidence_ids':references[claim['predicate']],'option_ids':[a['id'],b['id']]})
        result["precautions"] = ["Carry water and suitable footwear; check conditions again before leaving.","Postpone outdoor activity if thunder is heard; seek a substantial enclosed shelter."]
        if any(code.startswith('pollution_') for code in preferred['warning_codes']):
            result['precautions'].append('Modeled regional air quality is elevated: reduce intensity/duration, take breaks and consider postponing strenuous activity. This is a coarse forecast, not a local sensor.')
        if constraints.get("pollution_sensitive"):
            result["precautions"].append("Follow your existing clinician/asthma action plan; reduce intensity when air quality is poor. This regional forecast cannot establish personal safety.")
    render_answer(result,language)
    result['evidence'].append({'id':'air_quality_policy','kind':'planning_policy','url':'https://document.airnow.gov/air-quality-guide-for-particle-pollution.pdf','rule_version':RULE_VERSION,'note':'Conservative planning cutoffs informed by AirNow; not medical clearance.'})
    result["timing_ms"]["total"] = round((time.perf_counter()-started)*1000)
    await emit("complete", "Analysis complete")
    return result


async def perform(query,identifier,emit):
    global inflight
    if inflight>=settings.max_inflight:
        raise HTTPException(429,detail={"code":"capacity","request_id":identifier},headers={"Retry-After":"5"})
    inflight+=1
    try:
        if not await model.ready():
            raise HTTPException(503,detail={"code":"model_unavailable","message":"The configured Qwen endpoint is unavailable. Retry when it is ready.","request_id":identifier})
        async with asyncio.timeout(settings.deadline_seconds):
            return await run_query(query,identifier,emit)
    except HTTPException:
        raise
    except TimeoutError:
        raise HTTPException(504,detail={"code":"deadline","request_id":identifier})
    except (httpx.HTTPError,RuntimeError,ValueError,KeyError) as exc:
        logger.warning("analysis_failure request_id=%s kind=%s",identifier,type(exc).__name__)
        raise HTTPException(503,detail={"code":"source_or_model_failure","message":str(exc)[:180],"request_id":identifier}) from exc
    finally:
        inflight-=1


async def no_events(*_):
    pass


@app.get('/healthz')
async def health():
    return {"status":"alive"}


@app.get('/readyz')
async def ready():
    if not await model.ready():
        raise HTTPException(503,detail={"status":"model_not_loaded"})
    return {"status":"ready","inflight":inflight}


@app.get('/version')
async def version():
    return {"version":"0.1.0","model":settings.model_id,"model_revision":settings.model_revision,"rule_version":RULE_VERSION,"coding_ai":"OpenAI Codex","hosted_inference":False}


def prepare_conversation(query):
    try:session=conversation.begin(query.conversation_id)
    except KeyError as exc:raise HTTPException(404,detail=str(exc))
    except ValueError as exc:raise HTTPException(409,detail=str(exc))
    return query.model_copy(update={'conversation_id':session['id']}),session


def event_collector(events):
    clock=time.monotonic()
    async def emit(stage,message):
        nonlocal clock
        now=time.monotonic()
        if events:
            events[-1].update(status='complete',elapsed_ms=round((now-clock)*1000))
        events.append({'stage':stage,'message':message,'at':timestamp(),'status':'complete' if stage=='complete' else 'running','elapsed_ms':0 if stage=='complete' else None})
        clock=now
    return emit


@app.post('/v1/recommend')
@app.post('/ask')
async def recommend(query: Query):
    query,session=prepare_conversation(query)
    identifier=uuid.uuid4().hex
    events=[]
    try:
        result=await perform(query,identifier,event_collector(events))
        conversation.finish(session,query.question,identifier,events,result=result)
    except HTTPException as exc:
        conversation.finish(session,query.question,identifier,events,error={'http_status':exc.status_code,'detail':exc.detail})
        raise
    response=deepcopy(result)
    response['tool_events']=events
    if "hourly" not in query.include:
        for v in response.get("venues",[]):v.pop("hours",None)
        response.pop("matrix",None)
    if "geojson" not in query.include:response.pop("layers",None)
    return response


@app.get('/v1/conversations/{identifier}')
async def read_conversation(identifier: str):
    session=conversation.sessions.get(identifier)
    if not session:raise HTTPException(404,detail='Conversation expired. Start a new chat.')
    return {'conversation_id':identifier,'messages':session['messages'],'latest_result':session['result'],'busy':session['busy'],'active_analysis_id':session.get('active_analysis_id'),'pending_question':session.get('pending_question')}


@app.post('/v1/analyses',status_code=202)
async def create_analysis(query: Query):
    for key in list(jobs):
        if time.time()-jobs[key]['created']>1800 and jobs[key]['status']!='running':jobs.pop(key,None)
    if len(jobs)>=30:
        idle=sorted((key for key in jobs if jobs[key]['status']!='running'),key=lambda key:jobs[key]['created'])
        if not idle:raise HTTPException(429,detail='Analysis capacity is busy. Retry shortly.')
        jobs.pop(idle[0])
    query,session=prepare_conversation(query)
    identifier=uuid.uuid4().hex
    session['active_analysis_id']=identifier
    session['pending_question']=query.question
    job={'created':time.time(),'status':'running','events':[],'result':None,'query':query,'conversation_id':session['id']}
    jobs[identifier]=job
    emit=event_collector(job['events'])
    async def work():
        try:
            result=await perform(query,identifier,emit)
            job['result']=conversation.finish(session,query.question,identifier,job['events'],result=result)
            job['status']='complete'
        except HTTPException as exc:
            if job['events']:job['events'][-1]['status']='error'
            error={'http_status':exc.status_code,'detail':exc.detail}
            job.update(status='error',error=error)
            conversation.finish(session,query.question,identifier,job['events'],error=error)
        finally:session['active_analysis_id']=None
    job['task']=asyncio.create_task(work())
    return {'analysis_id':identifier,'conversation_id':session['id']}


def get_job(identifier):
    if identifier not in jobs:
        raise HTTPException(404,detail="Unknown or expired analysis")
    return jobs[identifier]


@app.get('/v1/analyses/{identifier}')
async def analysis(identifier: str):
    job=get_job(identifier)
    return {k:v for k,v in job.items() if k not in {"task","query","created"}}


@app.get('/v1/analyses/{identifier}/events')
async def events(identifier: str,request: Request):
    job=get_job(identifier)
    async def stream():
        cursor=0
        while not await request.is_disconnected():
            for item in job["events"][cursor:]:
                yield "data: "+json.dumps(item)+"\n\n"
            cursor=len(job["events"])
            if job["status"]!="running":
                yield "event: done\ndata: {}\n\n"
                break
            yield ": heartbeat\n\n"
            await asyncio.sleep(1)
    return StreamingResponse(stream(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})


class CompareRequest(BaseModel):
    before_id: str
    after_id: str


class ScenarioRequest(BaseModel):
    pollution_sensitive: bool


@app.post('/v1/analyses/{identifier}/scenario')
async def scenario(identifier: str,body: ScenarioRequest):
    job=get_job(identifier)
    original=job.get("result")
    if not original or not original.get("venues"):
        raise HTTPException(409,detail="No completed evidence snapshot")
    constraints={**original["normalized_intent"]["constraints"],"pollution_sensitive":body.pollution_sensitive}
    matrix=evaluate(original["venues"],[],original["normalized_intent"]["activity"],constraints)
    ordered=rank(matrix)
    return {**original,"status":"ok" if ordered else "no_suitable_option","matrix":matrix,"recommendations":ordered[:1],"alternatives":ordered[1:3],"avoid_windows":[o for o in matrix if o['eligibility']=='avoid'][:24],"normalized_intent":{**original['normalized_intent'],'pollution_sensitive':body.pollution_sensitive,'constraints':constraints},"explanations":[],"reasoning":{"mode":"deterministic_counterfactual","initial_interpretation_model":settings.model_id},"scenario":{"kind":"deterministic_rescore","changed":{"pollution_sensitive":body.pollution_sensitive},"source_snapshot":identifier,"computed_at":timestamp()},"answer":"Sensitivity scenario recomputed from the same retrieved evidence. Scores and avoidance policies reflect the changed constraint; no new measurements were invented."}


@app.post('/v1/analyses/{identifier}/compare')
async def compare_options(identifier: str, body: CompareRequest):
    job=get_job(identifier)
    if not job.get("result"):
        raise HTTPException(409,detail="Analysis not complete")
    options={o["id"]:o for o in job["result"].get("matrix",[])}
    if body.before_id not in options or body.after_id not in options:
        raise HTTPException(422,detail="Both options must belong to this snapshot")
    return {"snapshot_id":identifier,**compare(options[body.before_id],options[body.after_id])}


@app.get('/v1/showcase')
async def showcase():
    snapshot=Path("data/showcase.json")
    if not snapshot.exists():
        raise HTTPException(404,detail="No genuinely captured showcase exists yet")
    result=json.loads(snapshot.read_text(encoding='utf-8'))
    if result.get('rule_version')!=RULE_VERSION:
        raise HTTPException(404,detail='The captured analysis used an older policy. Run a fresh query.')
    return result
