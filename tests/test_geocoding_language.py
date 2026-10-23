import pytest

from geolens.config import settings
from geolens.sources import Sources


@pytest.mark.asyncio
@pytest.mark.parametrize(('original', 'expected'), [
    ('churchgate side', 'churchgate'),
    ('churchgate, Mumbai side', 'churchgate, Mumbai'),
    ('Churchgate side, Mumbai', 'Churchgate, Mumbai'),
    ('Riverside, Bengaluru', 'Riverside, Bengaluru'),
    ('East Side, Bengaluru', 'East Side, Bengaluru'),
    ('लोनावला, महाराष्ट्र', 'लोनावला, महाराष्ट्र'),
])
async def test_geocoder_removes_colloquial_side_without_guessing_city(monkeypatch, tmp_path, original, expected):
    monkeypatch.setattr(settings, 'database', str(tmp_path / 'cache.sqlite'))
    service = Sources()
    async def fetch(url, params, ttl):
        assert params['q'] == expected
        assert params['countrycodes'] == 'in'
        return [], {'url': url, 'cache': False}
    monkeypatch.setattr(service, 'fetch', fetch)
    try:
        _, meta = await service.geocode(original)
        assert meta['requested_text'] == original
        assert meta['resolved_query'] == expected
    finally:
        await service.client.aclose()
        service.db.close()
