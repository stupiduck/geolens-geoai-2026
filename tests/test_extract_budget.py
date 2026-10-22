import json,sqlite3
import pytest
from geolens.sources import Sources


def test_dense_roads_do_not_exhaust_the_venue_budget(tmp_path):
    path=tmp_path/'dense.sqlite'
    with sqlite3.connect(path) as db:
        db.executescript('CREATE TABLE metadata(key TEXT,value TEXT);CREATE TABLE features(id INTEGER PRIMARY KEY,data TEXT);CREATE VIRTUAL TABLE bounds_index USING rtree(id,minx,maxx,miny,maxy);')
        db.executemany('INSERT INTO metadata VALUES (?,?)',{'bounds':'[77,12,78,14]','import_complete':'true','source_url':'https://download.geofabrik.de/asia/india/southern-zone-latest.osm.pbf','downloaded_at':'2026-10-22'}.items())
        road=json.dumps({'type':'node','tags':{'highway':'crossing'}})
        db.executemany('INSERT INTO features VALUES (?,?)',((i,road) for i in range(20001)))
        db.executemany('INSERT INTO bounds_index VALUES (?,?,?,?,?)',((i,77.59,77.59,12.97,12.97) for i in range(20001)))
        db.execute('INSERT INTO features VALUES (?,?)',(20002,json.dumps({'id':42,'type':'node','tags':{'leisure':'park'}})))
        db.execute('INSERT INTO bounds_index VALUES (20002,77.59,77.59,12.97,12.97)')
    source=object.__new__(Sources)
    with pytest.raises(RuntimeError,match='feature budget'):
        source.extract_database(str(path),12.97,77.59,5)
    results,_=source.extract_database(str(path),12.97,77.59,5,'running')
    assert [r['id'] for r in results]==[42]
