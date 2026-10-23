from datetime import datetime
import pytest
from geolens import conversation
from geolens.app import app, model
from fastapi.testclient import TestClient


def prior():
    return {'request_id':'prior','normalized_intent':{'activity':'running','language':'hi','location':'पवई, मुंबई','constraints':{'pollution_sensitive':True,'duration_minutes':60,'start':'2026-10-24T06:00:00+05:30','end':'2026-10-24T10:00:00+05:30'}},'location':{'latitude':19.1,'longitude':72.9,'name':'Powai'},'recommendations':[{'time':'2026-10-24T07:00:00+05:30'}]}


def test_followup_retains_typed_health_place_and_language():
    source=prior()
    merged=conversation.merge(source,{'prefer_greener':True})
    assert merged['pollution_sensitive'] is True
    assert merged['language']=='hi'
    assert merged['location']=='पवई, मुंबई'
    assert merged['_location_changed'] is False
    assert merged['_time_range'][0].hour==6
    assert source['normalized_intent']['constraints'].get('prefer_greener') is None


def test_two_hours_later_anchors_recommendation_not_original_window():
    merged=conversation.merge(prior(),{'time_shift_hours':2})
    assert merged['_time_range'][0].hour==9
    assert (merged['_time_range'][1]-merged['_time_range'][0]).total_seconds()==3600


def test_only_explicit_clear_removes_retained_flag():
    assert conversation.merge(prior(),{'clear_flags':['pollution_sensitive']})['pollution_sensitive'] is False


def test_conversation_reserves_one_inflight_reply():
    session=conversation.begin()
    with pytest.raises(ValueError):conversation.begin(session['id'])
    conversation.finish(session,'message','test',[],error='fixture')
    assert conversation.begin(session['id']) is session
    session['busy']=False


def test_clarification_choice_preserves_original_query(monkeypatch):
    seen=[]
    async def ready():return True
    async def interpret(question):
        seen.append(question)
        return {'activity':'running','language':'hi','location':None,'time_expression':'tomorrow morning'},{}
    monkeypatch.setattr(model,'ready',ready)
    monkeypatch.setattr(model,'interpret',interpret)
    with TestClient(app) as client:
        reply=client.post('/v1/recommend',json={'question':'कहाँ दौड़ूँ?'}).json()
        assert reply['conversation_id']
        restored=client.get('/v1/conversations/'+reply['conversation_id']).json()
        assert restored['messages'][0]['question']=='कहाँ दौड़ूँ?'
        assert restored['latest_result']['normalized_intent']['language']=='hi'
        assert restored['messages'][0]['events'][0]['message']=='Interpreting activity and constraints'
    assert seen==['कहाँ दौड़ूँ?']


def test_followup_model_cannot_add_unmentioned_health_flags(monkeypatch):
    import asyncio
    seen={}
    async def generate(system,user,schema,tokens):
        seen.update(schema=schema)
        return {'activity':'running','location':'Powai','time_expression':None,'time_shift_hours':2,'radius_km':None,'duration_minutes':None,'set_flags':['pregnancy'],'clear_flags':[],'prefer_greener':False},{}
    monkeypatch.setattr(model,'generate',generate)
    patch,_=asyncio.run(model.followup('Two hours later',{'activity':'running','area':{'name':'Powai'},'language':'hi','constraints':{'pollution_sensitive':True}}))
    assert seen['schema']['properties']['set_flags']['maxItems']==0
    assert patch['set_flags']==[]
    assert patch['location'] is None
    assert patch['activity'] is None
    assert patch['prefer_greener'] is None
    assert patch['language']=='hi'
