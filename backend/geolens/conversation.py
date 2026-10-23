"""Bounded conversational memory and typed context, independent of the browser."""
import time
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from .engine import IST, compare

sessions = {}
FLAGS = ('pollution_sensitive','child_present','older_adult','pregnancy','avoid_steep_terrain','commute')


def begin(identifier=None):
    now=time.monotonic()
    for key in list(sessions):
        if now-sessions[key]['touched']>3600 and not sessions[key]['busy']:
            sessions.pop(key)
    if identifier:
        if identifier not in sessions:
            raise KeyError('Conversation expired. Start a new chat.')
        session=sessions[identifier]
        if session['busy']:
            raise ValueError('Wait for the current reply before sending another message.')
    else:
        if len(sessions)>=32:
            idle=sorted((s for s in sessions.values() if not s['busy']),key=lambda s:s['touched'])
            if not idle:
                raise ValueError('Conversation capacity is busy. Please retry shortly.')
            sessions.pop(idle[0]['id'])
        identifier=uuid.uuid4().hex
        session={'id':identifier,'messages':[],'result':None,'busy':False,'touched':now}
        sessions[identifier]=session
    session.update(busy=True,touched=now)
    return session


def context(result):
    if not result:return None
    intent=result.get('normalized_intent',{})
    constraints=intent.get('constraints',{})
    venues={v['id']:v for v in result.get('venues',[])}
    options=result.get('recommendations',[])+result.get('alternatives',[])
    return {'activity':intent.get('activity'),'language':intent.get('language','en'),
        'area':result.get('location') or intent.get('location'),
        'time_expression':intent.get('time_expression'),
        'constraints':constraints or {k:intent.get(k) for k in FLAGS},
        'recommended_time':options[0]['time'] if options else constraints.get('start'),
        'options':[{'id':o['venue_id'],'name':venues.get(o['venue_id'],{}).get('name'),'time':o['time']} for o in options[:3]]}


def merge(previous,patch):
    old=previous.get('normalized_intent',{})
    constraints=old.get('constraints',{})
    result={**old,'constraints':deepcopy(constraints)}
    for key in ('activity','location','time_expression','radius_km','duration_minutes'):
        if patch.get(key) is not None:result[key]=patch[key]
    for key in FLAGS:
        result[key]=bool(constraints.get(key,old.get(key,False)))
        if key in patch.get('set_flags',[]):result[key]=True
        if key in patch.get('clear_flags',[]):result[key]=False
    result['prefer_greener']=patch.get('prefer_greener') if patch.get('prefer_greener') is not None else constraints.get('prefer_greener',False)
    result['language']=patch.get('language') or old.get('language','en')
    result['_location_changed']=patch.get('location') is not None
    if patch.get('time_shift_hours') is not None:
        anchor=(previous.get('recommendations') or [{}])[0].get('time') or constraints.get('start')
        if anchor:
            start=datetime.fromisoformat(anchor)+timedelta(hours=patch['time_shift_hours'])
            duration=patch.get('duration_minutes') or constraints.get('duration_minutes',60)
            result['_time_range']=(start,start+timedelta(minutes=duration))
    elif patch.get('time_expression') is None and constraints.get('start') and constraints.get('end'):
        result['_time_range']=(datetime.fromisoformat(constraints['start']),datetime.fromisoformat(constraints['end']))
    return result


def change(previous,result):
    before=(previous.get('recommendations') or [None])[0] if previous else None
    after=(result.get('recommendations') or [None])[0]
    if not before or not after:return None
    return {**compare(before,after),'before_time':before['time'],'after_time':after['time'],
        'same_venue':before['venue_id']==after['venue_id'],
        'before_conditions':before['conditions'],'after_conditions':after['conditions']}


def finish(session,question,identifier,events,result=None,error=None):
    if events and events[-1].get('elapsed_ms') is None:
        events[-1].update(status='error' if error else 'complete',elapsed_ms=max(0,round((datetime.now(IST)-datetime.fromisoformat(events[-1]['at'])).total_seconds()*1000)))
    if result:
        result['conversation_id']=session['id']
        result['conversation_change']=change(session['result'],result)
        session['result']=result
    message={'id':identifier,'analysis_id':identifier,'question':question,'status':'complete' if result else 'error',
        'created_at':datetime.now(IST).isoformat(),'answer':result.get('answer','') if result else '',
        'language':result.get('normalized_intent',{}).get('language','en') if result else 'en',
        'recommendations':result.get('recommendations',[])[:1] if result else [],
        'venues':[{k:v[k] for k in ('id','name','lat','lon','distance_km')} for v in result.get('venues',[])] if result else [],
        'precautions':result.get('precautions',[]) if result else [],'explanations':result.get('explanations',[]) if result else [],
        'result_status':result.get('status') if result else None,'error':error,'events':deepcopy(events),
        'clarification':result.get('clarification') if result else None,
        'web_notices':result.get('web_notices') if result else None,
        'activity':result.get('normalized_intent',{}).get('activity') if result else None,
        'conversation_change':result.get('conversation_change') if result else None}
    session['messages']=(session['messages']+[message])[-20:]
    session.update(busy=False,touched=time.monotonic())
    return result
