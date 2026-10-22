from geolens.engine import evaluate
from test_decision import hours,venue


def test_sunset_photo_preference_uses_real_solar_geometry():
    h=hours()[:1]*2
    h=[{**h[0],'time':'2026-10-23T17:00:00+05:30'},{**h[1],'time':'2026-10-23T18:00:00+05:30'}]
    v=venue()
    v['tags']={'tourism':'viewpoint'}
    result=evaluate([v],h,'outdoor_photography',{'photography_goal':'sunset','duration_minutes':60})
    assert result[1]['score']>result[0]['score']
