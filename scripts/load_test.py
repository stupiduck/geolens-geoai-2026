"""Bounded local concurrency/resource measurements using actual model + source caches."""
import argparse
import asyncio
import json
import time
from pathlib import Path
import httpx
import psutil

p=argparse.ArgumentParser()
p.add_argument('--base-url',default='http://127.0.0.1:8000')
p.add_argument('--concurrency',type=int,default=2)
args=p.parse_args()

async def main():
    samples=[]
    running=True
    async def sample():
        while running:
            processes=[]
            for process in psutil.process_iter(['name','cmdline']):
                try:
                    command=' '.join(process.info['cmdline'] or [])
                    if process.info['name']=='llama-server.exe' or ('uvicorn' in command and 'geolens.app' in command):
                        processes.append({'pid':process.pid,'name':process.info['name'],'rss_mib':round(process.memory_info().rss/2**20,1),'cpu_percent':process.cpu_percent()})
                except (psutil.NoSuchProcess,psutil.AccessDenied):pass
            samples.append(processes)
            await asyncio.sleep(.5)
    async with httpx.AsyncClient(timeout=90) as client:
        async def request(index):
            start=time.perf_counter()
            r=await client.post(args.base_url+'/v1/recommend',json={'question':'Where should I run tomorrow morning near Powai, Mumbai?'})
            d=r.json()
            return {'index':index,'http_status':r.status_code,'seconds':round(time.perf_counter()-start,3),'status':d.get('status'),'detail':d.get('detail'),'timing_ms':d.get('timing_ms')}
        sampler=asyncio.create_task(sample())
        results=await asyncio.gather(*(request(i) for i in range(args.concurrency)))
        running=False
        await sampler
    report={'concurrency':args.concurrency,'results':results,'resource_samples':samples,'hardware':'Local Ryzen AI 9 HX 370, 24 logical processors; llama.cpp set to 2 threads; Windows RSS is not Linux container memory','peak_model_rss_mib':max((x['rss_mib'] for sample in samples for x in sample if x['name']=='llama-server.exe'),default=None)}
    Path(f'docs/load-test-{args.concurrency}.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='resource_samples'},indent=2))

asyncio.run(main())
