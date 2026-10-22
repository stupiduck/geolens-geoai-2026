"""Representative real model/source queries. Does not treat domain outcomes as recommendations."""
import asyncio,json,time
from pathlib import Path
import httpx

async def main():
    reports=json.loads(Path('docs/release-check.json').read_text(encoding='utf-8')) if Path('docs/release-check.json').exists() else []
    questions=[
        'Can I cycle to work tomorrow?',
        'Where should I hike tomorrow morning near Lonavala, Maharashtra?',
        'कल सुबह पवई मुंबई के पास दौड़ने के लिए कौन सी जगह बेहतर रहेगी?',
        'Where should I run tomorrow morning in Bengaluru, Karnataka?',
    ]
    async with httpx.AsyncClient(timeout=90) as client:
        for question in questions:
            if any(r['question']==question and r['http_status']==200 for r in reports):continue
            start=time.perf_counter()
            r=await client.post('http://127.0.0.1:8000/v1/recommend',json={'question':question,'include':['evidence','hourly','geojson']})
            data=r.json()
            report={'question':question,'seconds':round(time.perf_counter()-start,3),'http_status':r.status_code,'status':data.get('status'),'intent':data.get('normalized_intent'),'location':data.get('location'),'venues':len(data.get('venues',[])),'detail':data.get('detail'),'answer':data.get('answer'),'timing_ms':data.get('timing_ms'),'evidence':data.get('evidence')}
            reports.append(report)
            Path('docs/release-check.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({k:v for k,v in report.items() if k not in {'evidence','intent'}},ensure_ascii=True),flush=True)

asyncio.run(main())
