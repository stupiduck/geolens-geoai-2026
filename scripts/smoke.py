"""Real local HTTP smoke test. A captured showcase is created only from a genuine ok result."""
import argparse
import asyncio
import json
import time
from pathlib import Path
import httpx

p=argparse.ArgumentParser()
p.add_argument('--base-url',default='http://127.0.0.1:8000')
p.add_argument('--capture',action='store_true')
args=p.parse_args()

async def main():
    reports=[]
    captured=False
    async with httpx.AsyncClient(timeout=90) as client:
        for question in ['Where should I run tomorrow morning near Powai, Mumbai?','कल सुबह पवई मुंबई के पास दौड़ने के लिए कौन सी जगह बेहतर रहेगी?']:
            begin=time.perf_counter()
            response=await client.post(args.base_url+'/v1/recommend',json={'question':question,'include':['evidence','hourly','geojson']})
            data=response.json()
            report={'question':question,'http_status':response.status_code,'elapsed_seconds':round(time.perf_counter()-begin,3),'result':data}
            reports.append(report)
            print(json.dumps({k:v for k,v in report.items() if k!='result'},ensure_ascii=False),flush=True)
            print(json.dumps({'status':data.get('status'),'answer':data.get('answer'),'venues':len(data.get('venues',[])),'detail':data.get('detail')},ensure_ascii=False),flush=True)
            if args.capture and response.status_code==200 and data.get('status')=='ok' and not captured:
                captured=True
                data['snapshot_label']='Genuinely captured live analysis; inspect generated_at. Not a fresh query.'
                Path('data/showcase.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    Path('docs/live-smoke.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')

asyncio.run(main())
