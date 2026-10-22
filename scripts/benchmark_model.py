"""Measure actual local JSON intent/comparison, English/Hindi, and process resources."""
import asyncio
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from geolens.model import model

async def main():
    report={'model':'Qwen/Qwen3.5-2B','quantization':'Q4_K_M','threads':2,'context':4096,'thinking':False,'host':'local AMD Ryzen AI 9 HX 370; not production server','cases':[]}
    for question in ['Where should I run tomorrow morning near Powai, Mumbai?','कल सुबह पवई मुंबई के पास दौड़ने के लिए कौन सी जगह बेहतर रहेगी?','I have asthma. Find outdoor tennis tomorrow evening within 5 km of Bandra, Mumbai.']:
        try:
            start=time.perf_counter()
            value,timing=await model.interpret(question)
            report['cases'].append({'question':question,'json':value,'timing':timing,'wall_seconds':round(time.perf_counter()-start,3)})
        except Exception as e:report['cases'].append({'question':question,'error':str(e)})
    try:
        import psutil
        report['processes']=[{'name':p.info['name'],'rss_mib':round(p.memory_info().rss/2**20,1),'cpu_seconds':sum(p.cpu_times()[:2])} for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower()=='llama-server.exe']
    except ImportError:pass
    Path('docs/model-benchmark.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    await model.client.aclose()

asyncio.run(main())
