"""Retrieve a public Geofabrik regional extract; keep its provenance for import."""
import argparse
import json
import urllib.request
from pathlib import Path
from datetime import datetime,timezone
from prepare_local_model import download

p=argparse.ArgumentParser()
p.add_argument('--region',choices=['western-zone','southern-zone','northern-zone','central-zone','eastern-zone','north-eastern-zone'],default='western-zone')
args=p.parse_args()
url=f'https://download.geofabrik.de/asia/india/{args.region}-latest.osm.pbf'
directory=Path('data/extracts');directory.mkdir(parents=True,exist_ok=True)
with urllib.request.urlopen(urllib.request.Request(url,method='HEAD'),timeout=30) as response:
    length=response.headers.get('Content-Length')
    modified=response.headers.get('Last-Modified')
path=directory/f'{args.region}.osm.pbf'
print(json.dumps({'source':url,'bytes':length,'last_modified':modified}),flush=True)
download(url,path,int(length) if length else None)
path.with_suffix('.provenance.json').write_text(json.dumps({'source_url':url,'downloaded_at':datetime.now(timezone.utc).isoformat(),'last_modified':modified,'licence':'ODbL','attribution':'© OpenStreetMap contributors / Geofabrik'},indent=2))
print('Downloaded:',path,flush=True)
