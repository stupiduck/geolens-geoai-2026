"""Real asynchronous HTTP flow, immutable comparison and policy counterfactual."""
import asyncio,json,time
from pathlib import Path
import httpx

async def main():
    async with httpx.AsyncClient(base_url='http://127.0.0.1:8000',timeout=90) as c:
        start=time.perf_counter()
        r=await c.post('/v1/analyses',json={'question':'Where should I run tomorrow morning near Powai, Mumbai?','include':['evidence','hourly','geojson']})
        r.raise_for_status();identifier=r.json()['analysis_id']
        for _ in range(160):
            job=(await c.get('/v1/analyses/'+identifier)).json()
            if job['status']!='running':break
            await asyncio.sleep(.5)
        assert job['status']=='complete',job
        data=job['result'];assert data['status']=='ok',data['status']
        before=data['recommendations'][0]
        after=next(o for o in data['matrix'] if o['venue_id']==before['venue_id'] and o['time']!=before['time'])
        r=await c.post(f'/v1/analyses/{identifier}/compare',json={'before_id':before['id'],'after_id':after['id']});r.raise_for_status();comparison=r.json()
        assert abs(comparison['score_delta']-(after['score']-before['score']))<.011
        r=await c.post(f'/v1/analyses/{identifier}/scenario',json={'pollution_sensitive':True});r.raise_for_status();scenario=r.json()
        assert scenario['normalized_intent']['constraints']['pollution_sensitive']
        assert scenario['normalized_intent']['pollution_sensitive']
        for o in scenario['matrix']:
            if o['conditions'].get('us_aqi',0)>=151:
                assert o['eligibility'] in {'avoid','excluded'}
        report={'http_status':200,'elapsed_seconds':round(time.perf_counter()-start,3),'request_id':identifier,'venues':len(data['venues']),'comparison':comparison,'scenario_status':scenario['status'],'scenario_policy_consistent':True}
        Path('docs/interactions.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report))

asyncio.run(main())
