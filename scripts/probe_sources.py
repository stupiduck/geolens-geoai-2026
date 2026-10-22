import asyncio
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from geolens.sources import Sources


async def main():
    sources=Sources()
    report={}
    for name,operation in [("geocoding",lambda:sources.geocode("Powai, Mumbai, India")),("venues",lambda:sources.venues(19.11872,72.90735,3,"running"))]:
        try:
            data,meta=await operation()
            report[name]={"ok":True,"count":len(data),"metadata":meta,"sample":data[:2]}
        except Exception as exc:
            report[name]={"ok":False,"error":str(exc)}
    venues=[{"id":"probe-coordinate","lat":19.11872,"lon":72.90735}]
    try:
        report["forecasts"]={"ok":True,"metadata":await sources.forecasts(venues),"sample":venues[0]["hours"][:1]}
    except Exception as exc:
        report["forecasts"]={"ok":False,"error":str(exc)}
    print(json.dumps(report,ensure_ascii=False,indent=2))
    await sources.client.aclose()


if __name__=="__main__":
    asyncio.run(main())
