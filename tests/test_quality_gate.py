from copy import deepcopy
from datetime import datetime, timedelta
import pytest
from geolens.engine import evaluate, ACTIVITIES, IST, RAIN_LIMITS
from geolens.app import rank, run_query, Query, no_events, model, sources
from geolens.narrative import render


def fixture():
    time=(datetime.now(IST)+timedelta(days=1)).replace(hour=8,minute=0,second=0,microsecond=0)
    hour={'time':time.isoformat(),'temperature':25,'apparent_temperature':25,'rain_probability':0,'rain_mm':0,'wind_kmh':5,'weather_code':0,'is_day':1,'us_aqi':30}
    return {'id':'way/1','name':'Test Park','lat':12.97,'lon':77.59,'distance_km':1,'tags':{'name':'Test Park','leisure':'park','access':'yes'},'features':{},'hours':[hour,{**hour,'time':(time+timedelta(hours=1)).isoformat()}]}


@pytest.mark.parametrize('activity',list(ACTIVITIES))
def test_96_percent_rain_is_not_an_eligible_recommendation(activity):
    v=fixture();v['tags'].update(sport={'tennis':'tennis','football':'soccer','cricket':'cricket','golf':'golf'}.get(activity,''))
    v['hours'][1]['rain_probability']=96
    options=evaluate([v],[],activity,{'duration_minutes':120})
    assert options[0]['eligibility']!='eligible'
    assert 'high_rain_probability' in options[0]['warning_codes']
    assert not rank(options)


def test_rain_amount_and_missing_weather_cannot_hide_behind_high_score():
    for field,value in [('rain_mm',5),('rain_probability',None),('wind_kmh',None)]:
        v=fixture();v['hours'][0][field]=value
        assert evaluate([v],[],'picnic',{'duration_minutes':120})[0]['eligibility']!='eligible'


def test_unnamed_picnic_node_is_comparison_only():
    v=fixture();v['name']='Unnamed picnic location · OSM 1';v['tags'].pop('name')
    result=evaluate([v],[],'picnic',{'duration_minutes':120})[0]
    assert result['eligibility']=='insufficient_data'
    assert 'unverified_picnic_destination' in result['limitations']
    assert not rank([result])


def test_named_node_without_destination_footprint_is_not_promoted():
    v=fixture();v['metadata']={'destination_evidence_sufficient':False,'footprint_area_m2':None}
    result=evaluate([v],[],'picnic',{'duration_minutes':120})[0]
    assert result['eligibility']=='insufficient_data'


@pytest.mark.parametrize('activity',list(ACTIVITIES))
def test_activity_rain_boundary_is_consistent_for_identical_profiles(activity):
    v=fixture();v['tags'].update(sport={'tennis':'tennis','football':'soccer','cricket':'cricket','golf':'golf'}.get(activity,''))
    threshold=RAIN_LIMITS[activity][0]
    for probability,expected in [(threshold-1,'eligible'),(threshold,'avoid')]:
        for profile in [{},{'child_present':True}]:
            v['hours'][0]['rain_probability']=probability
            result=evaluate([v],[],activity,{**profile,'duration_minutes':120})[0]
            assert result['eligibility']==expected


def test_ranking_excludes_high_scoring_restricted_options_and_uses_bounds():
    options=[{'id':'restricted','eligibility':'excluded','score':99,'score_low':99,'venue_id':'a','time':'08:00'},
             {'id':'uncertain','eligibility':'eligible','score':76,'score_low':70,'venue_id':'b','time':'08:00'},
             {'id':'supported','eligibility':'eligible','score':73,'score_low':73,'venue_id':'c','time':'08:00'}]
    assert [o['id'] for o in rank(options)]==['supported','uncertain']


def test_all_unsuitable_answer_is_explicit_in_both_languages():
    v=fixture();v['hours'][0]['rain_probability']=96
    options=evaluate([v],[],'picnic',{'duration_minutes':120})
    for lang in ['en','hi']:
        result={'status':'no_suitable_option','normalized_intent':{'activity':'picnic'},'matrix':options,'answer':'old recommendation','recommendations':[options[0]]}
        render(result,lang)
        assert not result['recommendations']
        assert ('No suitable' if lang=='en' else 'उपयुक्त विकल्प नहीं') in result['answer']
        assert 'rain' in result['answer'].lower() if lang=='en' else 'बारिश' in result['answer']


@pytest.mark.asyncio
async def test_model_cannot_promote_lower_ranked_candidate(monkeypatch):
    a=fixture();b=deepcopy(a);b.update(id='way/2',name='Farther Park',distance_km=4)
    async def interpret(_):return {'activity':'picnic','language':'en','location':'Bengaluru','time_expression':'tomorrow morning'},{}
    async def venues(*_):return [a,b],{'mode':'fixture'}
    async def features(*_):return {'status':'unavailable'}
    async def reason(options,_):return {'preferred_id':options[-1]['id'],'claims':[]},{}
    monkeypatch.setattr(model,'interpret',interpret);monkeypatch.setattr(model,'reason',reason)
    monkeypatch.setattr(sources,'venues',venues);monkeypatch.setattr(sources,'features',features)
    # Actual adapter mutates each venue with hours; return only source metadata.
    async def forecast_meta(_):return {'weather':{},'air_quality':{}}
    monkeypatch.setattr(sources,'forecasts',forecast_meta)
    result=await run_query(Query(question='Picnic tomorrow morning',location={'latitude':12.97,'longitude':77.59}),'test',no_events)
    assert result['recommendations'][0]['id']==rank(result['matrix'])[0]['id']
    assert result['reasoning']['preferred_id']==result['recommendations'][0]['id']
