"""Browser-independent HTTP API and immutable analysis snapshots."""
import asyncio
import json
import logging
import re
import time
import uuid
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
    intent, it = await model.interpret(query.question)
    language = intent["language"] if query.language=="auto" else query.language
    activity = query.activity or intent["activity"]
    result["normalized_intent"] = intent
    result["timing_ms"] = {"intent":it}
    if activity not in ACTIVITIES:
        return {**result,"status":"out_of_scope","answer":"Please choose an outdoor activity: running, cycling, golf, cricket, football, tennis, hiking, picnic, outdoor gathering or photography."}
    if intent.get("commute"):
        return {**result,"status":"needs_clarification","answer":"Please supply your starting area and destination for commute planning. Route-level commute analysis is not yet available in this build.","clarification":{"fields":["origin","destination"]}}
    location = query.location or Location(text=intent.get("location"))
    if location.latitude is None and not location.text:
        return {**result,"status":"needs_clarification","answer":"कृपया अपना इलाका या शहर बताएं।" if language=="hi" else "Which area or city should I search near?","clarification":{"fields":["location"]}}
    now = datetime.now(IST)
    start,end = resolve_time(intent.get("time_expression") or query.question,now)
    if query.time_range:
        start,end = query.time_range.start.astimezone(IST),query.time_range.end.astimezone(IST)
    if end<=now or start>now+timedelta(days=7):
        return {**result,"status":"needs_clarification","answer":"Please choose a future time within the next seven days."}
    radius = query.radius_km or intent.get("radius_km") or 5
    duration = query.duration_minutes or intent.get("duration_minutes") or DURATIONS.get(activity,60)
    if not .5<=radius<=50 or not 15<=duration<=360:
        return {**result,"status":"needs_clarification","answer":"Please use a radius between 0.5–50 km and duration between 15–360 minutes."}
    constraints = {k:bool(intent.get(k)) for k in ("pollution_sensitive","child_present","older_adult","pregnancy","avoid_steep_terrain")}
    if query.profile:
        constraints.update(query.profile.model_dump(exclude_unset=True))
    if query.constraints:
        constraints.update(query.constraints.model_dump(exclude_unset=True))
    constraints.update({"radius_km":radius,"duration_minutes":duration,"start":start.isoformat(),"end":end.isoformat()})
    result["assumptions"] = [f"Search radius: {radius:g} km straight-line; activity duration: {duration} minutes.",f"Evaluated local start times: {start.isoformat()} to {end.isoformat()}."]
    result["normalized_intent"].update({"activity":activity,"constraints":constraints,"language":language})
    await emit("location", "Resolving the search area")
    if location.latitude is not None:
        lat,lon = location.latitude,location.longitude
        # Coordinates are explicit user input; never silently substitute a city.
        if not (6<=lat<=38 and 68<=lon<=98):
            return {**result,"status":"out_of_scope","answer":"This prototype supports Indian search areas."}
        name = f"{lat:.4f}, {lon:.4f}"
    else:
        places,meta = await sources.geocode(location.text)
        result["evidence"].append({"id":"location","kind":"mapped_feature",**meta})
        if not places:
            return {**result,"status":"needs_clarification","answer":"I could not resolve that Indian location. Add the city/state or choose coordinates."}
        # Same named area in different states/cities needs a deliberate choice.
        if len(places)>1 and places[0].get("address",{}).get("state")!=places[1].get("address",{}).get("state"):
            return {**result,"status":"needs_clarification","answer":"Which location did you mean?","clarification":{"fields":["location"],"choices":[p["display_name"] for p in places]}}
        lat,lon,name = float(places[0]["lat"]),float(places[0]["lon"]),places[0]["display_name"]
    result["location"] = {"latitude":lat,"longitude":lon,"name":name,"radius_km":radius}
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
            "answer":f"{best['name']} — {time_label} IST. उपयुक्तता {preferred['score_low']:.0f}–{preferred['score_high']:.0f}/100। प्रवेश और समय की पुष्टि करें।" if language=="hi" else f"{best['name']} at {time_label} IST: heuristic suitability {preferred['score_low']:.0f}–{preferred['score_high']:.0f}/100. Confirm access and opening hours."})
        if near_tie:
            result["answer"] += " Close alternatives remain plausible because score ranges overlap."
        result["precautions"] = ["Carry water and suitable footwear; check conditions again before leaving.","Postpone outdoor activity if thunder is heard; seek a substantial enclosed shelter."]
        if constraints.get("pollution_sensitive"):
            result["precautions"].append("Follow your existing clinician/asthma action plan; reduce intensity when air quality is poor. This regional forecast cannot establish personal safety.")
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
            raise HTTPException(503,detail={"code":"model_unavailable","message":"Start the local llama.cpp server before requesting analysis.","request_id":identifier})
        async with asyncio.timeout(settings.deadline_seconds):
            return await run_query(query,identifier,emit)
    except HTTPException:
        raise
    except TimeoutError:
        raise HTTPException(504,detail={"code":"deadline","request_id":identifier})
    except (httpx.HTTPError,RuntimeError,ValueError) as exc:
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


@app.post('/v1/recommend')
@app.post('/ask')
async def recommend(query: Query):
    result = await perform(query,uuid.uuid4().hex,no_events)
    if "hourly" not in query.include:
        for v in result.get("venues",[]):
            v.pop("hours",None)
        result.pop("matrix",None)
    if "geojson" not in query.include:
        result.pop("layers",None)
    return result


@app.post('/v1/analyses',status_code=202)
async def create_analysis(query: Query):
    # Prune retained snapshots to a small fixed bound and TTL.
    for key in list(jobs):
        if time.time()-jobs[key]["created"]>1800 and jobs[key]["status"]!="running":
            jobs.pop(key,None)
    if len(jobs)>=30:
        raise HTTPException(429,detail="Snapshot capacity reached; retry after older analyses expire")
    identifier=uuid.uuid4().hex
    job={"created":time.time(),"status":"running","events":[],"result":None,"query":query}
    jobs[identifier]=job
    async def emit(stage,message):
        job["events"].append({"stage":stage,"message":message,"at":timestamp()})
    async def work():
        try:
            job["result"]=await perform(query,identifier,emit)
            job["status"]="complete"
        except HTTPException as exc:
            job.update({"status":"error","error":{"http_status":exc.status_code,"detail":exc.detail}})
    job["task"]=asyncio.create_task(work())
    return {"analysis_id":identifier}


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
    return {**original,"matrix":matrix,"recommendations":ordered[:1],"alternatives":ordered[1:3],"scenario":{"kind":"deterministic_rescore","changed":{"pollution_sensitive":body.pollution_sensitive},"source_snapshot":identifier},"answer":"Sensitivity scenario recomputed from the same retrieved evidence. Scores and avoidance policies reflect the changed constraint; no new measurements were invented."}


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
    return json.loads(snapshot.read_text(encoding="utf-8"))
