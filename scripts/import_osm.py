"""Stream a genuine Geofabrik PBF into bounded-query SQLite + RTree. No answers stored.

Usage: python scripts/import_osm.py region.osm.pbf --source-url https://download.geofabrik.de/... --bounds west,south,east,north
Bounds must describe the extract's COMPLETE covered rectangle, not an invented larger area.
For a regional polygon extract use a conservative interior rectangle, or import a clipped
rectangle known to be covered. Queries outside that rectangle refuse the fallback.
"""
import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import osmium
from shapely.geometry import shape


class Importer(osmium.SimpleHandler):
    def __init__(self,db):
        super().__init__()
        self.db=db
        self.factory=osmium.geom.GeoJSONFactory()
        self.count=0
        self.bounds=json.loads(db.execute("SELECT value FROM metadata WHERE key='bounds'").fetchone()[0])

    def relevant(self,tags):
        return any(k in tags for k in ("leisure","sport","tourism","highway","route","natural")) or tags.get("landuse") in {"industrial","forest","grass","recreation_ground"}

    def store(self,kind,obj,geojson):
        tags=dict(obj.tags)
        if not self.relevant(tags):
            return
        geometry=json.loads(geojson)
        g=shape(geometry)
        if g.is_empty:
            return
        w,s,e,n=g.bounds
        bw,bs,be,bn=self.bounds
        if e<bw or w>be or n<bs or s>bn:
            return
        self.count+=1
        data={"id":obj.id,"type":kind,"tags":tags,"geojson":geometry}
        self.db.execute("INSERT INTO features VALUES (?,?)",(self.count,json.dumps(data)))
        self.db.execute("INSERT INTO bounds_index VALUES (?,?,?,?,?)",(self.count,w,e,s,n))
        if self.count%10000==0:
            self.db.commit()
            print("Features imported:",self.count,flush=True)

    def node(self,n):
        if self.relevant(n.tags):
            self.store("node",n,self.factory.create_point(n))

    def way(self,w):
        if self.relevant(w.tags):
            try:
                self.store("way",w,self.factory.create_linestring(w))
            except osmium.InvalidLocationError:
                pass

    def area(self,a):
        if self.relevant(a.tags):
            try:
                # Area tags preserve genuine polygons, not a center masquerading as area.
                obj=type("AreaObject",(),{"id":a.orig_id(),"tags":a.tags})()
                self.store("way" if a.from_way() else "relation",obj,self.factory.create_multipolygon(a))
            except (osmium.InvalidLocationError,RuntimeError):
                pass


def main():
    p=argparse.ArgumentParser()
    p.add_argument("pbf",type=Path)
    p.add_argument("--source-url",required=True)
    p.add_argument("--bounds",required=True)
    p.add_argument("--output",default="data/osm.sqlite")
    args=p.parse_args()
    bounds=[float(v) for v in args.bounds.split(",")]
    if len(bounds)!=4 or bounds[0]>=bounds[2] or bounds[1]>=bounds[3]:
        p.error("Invalid west,south,east,north bounds")
    if not args.source_url.startswith("https://download.geofabrik.de/"):
        p.error("Record the real Geofabrik source URL")
    output=Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():
        p.error("Output exists; write a new version then replace explicitly")
    with sqlite3.connect(output) as db:
        db.executescript("CREATE TABLE features(id INTEGER PRIMARY KEY,data TEXT); CREATE VIRTUAL TABLE bounds_index USING rtree(id,minx,maxx,miny,maxy); CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);")
        header=osmium.io.Reader(str(args.pbf)).header()
        metadata={"source_url":args.source_url,"downloaded_at":datetime.fromtimestamp(args.pbf.stat().st_mtime,timezone.utc).isoformat(),"imported_at":datetime.now(timezone.utc).isoformat(),"osm_timestamp":header.get("osmosis_replication_timestamp"),"bounds":json.dumps(bounds),"licence":"ODbL","attribution":"© OpenStreetMap contributors / Geofabrik"}
        db.executemany("INSERT INTO metadata VALUES (?,?)",metadata.items())
        handler=Importer(db)
        # File-backed node cache avoids loading a country's node index into RAM.
        node_cache=output.with_suffix(".nodecache")
        handler.apply_file(str(args.pbf),locations=True,idx="sparse_file_array,"+str(node_cache))
        db.execute("INSERT OR REPLACE INTO metadata VALUES ('import_complete','true')")
        db.commit()
        print(json.dumps({"output":str(output),"features":handler.count,"metadata":metadata}))
        node_cache.unlink(missing_ok=True)


if __name__=="__main__":
    main()
