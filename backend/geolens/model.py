"""One resident local model. No hosted inference or cosmetic fallback answer."""
import asyncio
import json
import time
import re
import httpx
from .config import settings
from .engine import ACTIVITIES


def explicit_location(question):
    """Keep an explicit geographic clause intact, independently of SLM shortening."""
    match=re.search(r'\b(?:near|around|in)\s+(.+?)(?=\s+(?:tomorrow|today|tonight|this\s+(?:weekend|evening)|next|on\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)|for\s+(?:a\s+)?\d|with|while|without|to\s+(?:run|cycle|hike))\b|[?!;]|$)',question,re.I)
    if match:
        value=match.group(1).strip(' ,.')
        if value and not re.match(r'^(?:the\s+)?(?:morning|evening|afternoon|rain|heat)\b',value,re.I):
            return value
    match=re.search(r'([\u0900-\u097f\w ,]+?)\s+(?:के पास|के आसपास|में)\b',question)
    if match:
        value=re.sub(r'^(?:कल|आज|इस|सुबह|शाम|दोपहर|सप्ताहांत|\s)+','',match.group(1)).strip(' ,')
        return value or None
    return None


def explicit_commute(question):
    return bool(re.search(r'\bcommut(?:e|ing)\b|\b(?:to|from)\s+(?:my\s+)?(?:work|office|school|college)\b|दफ्तर|ऑफिस|आवागमन',question,re.I))


def validate_claims(claims, options):
    valid = []
    for claim in claims:
        a, b = options.get(claim.get("subject")), options.get(claim.get("object"))
        if a is None or b is None:
            raise ValueError("Unknown evidence option")
        predicate = claim.get("predicate")
        if predicate == "higher_score":
            truth = a["score"] >= b["score"]
        elif predicate in {"cooler_than", "less_rain_than", "cleaner_regional_air"}:
            variable = {"cooler_than": "temperature", "less_rain_than": "rain_probability", "cleaner_regional_air": "us_aqi"}[predicate]
            x, y = a["conditions"].get(variable), b["conditions"].get(variable)
            truth = x is not None and y is not None and x < y
        elif predicate == "regional_aq_shared":
            x, y = a["conditions"].get("us_aqi"), b["conditions"].get("us_aqi")
            truth = x is not None and x == y
        elif predicate in {'lower_thermal_penalty','lower_road_proxy','shorter_trip'}:
            factor={'lower_thermal_penalty':'thermal','lower_road_proxy':'road_industry','shorter_trip':'travel'}[predicate]
            x=next((c['penalty'] for c in a.get('contributions',[]) if c['factor']==factor),None)
            y=next((c['penalty'] for c in b.get('contributions',[]) if c['factor']==factor),None)
            truth=x is not None and y is not None and x<y
        else:
            truth = False
        if not truth:
            raise ValueError("Unsupported comparative claim")
        valid.append(claim)
    return valid


class LocalModel:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.client = httpx.AsyncClient(timeout=40)

    async def ready(self):
        try:
            if (await self.client.get(settings.model_url + "/health", timeout=2)).status_code != 200:
                return False
            props=await self.client.get(settings.model_url+'/props',timeout=2)
            expected=settings.model_id.rsplit('/',1)[-1].casefold()
            return props.status_code==200 and expected in props.json().get('model_path','').casefold()
        except httpx.HTTPError:
            return False

    async def generate(self, system, user, schema, tokens=200):
        begin = time.perf_counter()
        async with self.lock:
            result = await self.client.post(settings.model_url + "/v1/chat/completions", json={
                "model": settings.model_id, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "temperature": 0, "max_tokens": tokens, "stream": False,
                "chat_template_kwargs": {"enable_thinking": False},
                "response_format": {"type": "json_schema", "json_schema": {"name": "geolens", "strict": True, "schema": schema}},
            })
            result.raise_for_status()
            payload = result.json()
            content = payload["choices"][0]["message"]["content"]
            return json.loads(content), {"elapsed_ms": round((time.perf_counter()-begin)*1000), "usage": payload.get("usage", {})}

    async def interpret(self, question):
        schema = {"type": "object", "additionalProperties": False, "properties": {
            "activity": {"type": "string", "enum": list(ACTIVITIES) + ["unknown"]},
            "location": {"type": ["string", "null"]},
            "time_expression": {"type": "string"},
            "radius_km": {"type": ["number", "null"]},
            "duration_minutes": {"type": ["integer", "null"]},
            "flags": {"type":"array","items":{"type":"string","enum":["pollution_sensitive","child_present","older_adult","pregnancy","avoid_steep_terrain","commute"]}}},
            "required": ["activity", "location", "time_expression", "radius_km", "duration_minutes", "flags"]}
        result,timing=await self.generate(
            "Extract outdoor intent as JSON. Preserve the FULL location phrase including neighborhood and city, in its original script. Hindi example: औंध पुणे stays औंध पुणे, not just पुणे. Keep relative time words verbatim. Asthma/अस्थमा/दमा means pollution_sensitive. Child/parents/pregnancy and avoiding hills are flags only if stated. Walk=nature walk=hiking; jogging=running; sunset photos=outdoor_photography. Unknown place/radius/duration=null. No health detail means flags=[]. Never guess a place.", question, schema, 150)
        flags=set(result.pop('flags',[]))
        if explicit_location(question):
            result['location']=explicit_location(question)
        if explicit_commute(question):
            flags.add('commute')
        text=question.lower()
        # Explicit mention safeguards cannot be erased by a small-model omission.
        if re.search(r'\b(asthma|asthmatic|pollution.sensitive)\b|अस्थमा|दमा|प्रदूषण.*संवेदनशील',text):
            flags.add('pollution_sensitive')
        for key in ('pollution_sensitive','child_present','older_adult','pregnancy','avoid_steep_terrain','commute'):
            result[key]=key in flags
        result['language']='hi' if re.search('[\u0900-\u097f]',question) else 'en'
        return result,timing

    async def reason(self, options, constraints):
        aliases={chr(65+i):o for i,o in enumerate(options)}
        # Enumerate verifiable relationships BEFORE the model selects its trade-offs.
        # This constrains facts while retaining model interpretation, option selection
        # and evidence prioritization; it does not substitute a canned answer.
        claims={}
        predicates=['lower_thermal_penalty','lower_road_proxy','shorter_trip','cooler_than','less_rain_than','cleaner_regional_air','regional_aq_shared','higher_score']
        for subject,a in aliases.items():
            for obj,b in aliases.items():
                if subject==obj:
                    continue
                count=0
                for predicate in predicates:
                    claim={'predicate':predicate,'subject':a['id'],'object':b['id']}
                    try:
                        validate_claims([claim],{a['id']:a,b['id']:b})
                    except ValueError:
                        continue
                    key=f'c{len(claims)}'
                    claims[key]=(claim,{'id':key,'predicate':predicate,'subject':subject,'object':obj})
                    count+=1
                    if count==2:
                        break
        schema={'type':'object','additionalProperties':False,'properties':{
            'preferred_id':{'type':'string','enum':list(aliases)},
            'claim_ids':{'type':'array','minItems':1 if claims else 0,'maxItems':2 if claims else 0,'items':{'type':'string',**({'enum':list(claims)} if claims else {})}}},'required':['preferred_id','claim_ids']}
        brief=[{'id':alias,'score':o['score'],'bounds':[o['score_low'],o['score_high']],'temperature':o['conditions'].get('temperature'),'us_aqi':o['conditions'].get('us_aqi'),'penalties':{c['factor']:round(c['penalty'],3) if c['penalty'] is not None else None for c in o['contributions'] if c['factor'] in {'thermal','travel','road_industry'}}} for alias,o in aliases.items()]
        result,timing=await self.generate(
            'Compare real eligible options for this person. Select a strong option using score bounds and relevant trade-offs. Choose 1 or 2 supplied TRUE claim_ids that explain your selection or a meaningful alternative. Prefer explanatory factors to simply higher_score. Lower penalties are better. For a sensitive person prioritize air quality and road context. Unknown is not zero. Return only the chosen option and claim IDs.',
            json.dumps({'sensitive':any(constraints.get(k) for k in ['pollution_sensitive','child_present','older_adult','pregnancy']),'options':brief,'verified_claims':[entry[1] for entry in claims.values()]},ensure_ascii=False,separators=(',',':')),schema,65)
        chosen=aliases[result['preferred_id']]
        if chosen['eligibility']!='eligible':
            raise ValueError('Model chose an ineligible option')
        selected=[claims[key][0] for key in dict.fromkeys(result['claim_ids'])]
        validate_claims(selected,{o['id']:o for o in options})
        return {'preferred_id':chosen['id'],'claims':selected,'reasoning_mode':'model-selected verified comparative relations'},timing


model = LocalModel()
