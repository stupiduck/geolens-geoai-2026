from geolens.sources import deduplicate_elements


def test_way_area_duplicate_keeps_one_polygon():
    line={'type':'way','id':1,'tags':{'name':'Fixture Park'},'geojson':{'type':'LineString','coordinates':[[72.9,19.1],[72.91,19.1],[72.91,19.11],[72.9,19.1]]}}
    area={'type':'way','id':1,'tags':{'name':'Fixture Park'},'geojson':{'type':'Polygon','coordinates':[[[72.9,19.1],[72.91,19.1],[72.91,19.11],[72.9,19.1]]]}}
    result=deduplicate_elements([line,area])
    assert len(result)==1
    assert result[0]['geojson']['type']=='Polygon'
