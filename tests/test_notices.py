import asyncio
import json

import httpx

from geolens.config import Settings
from geolens.notices import Notices, should_search


LOCATION = {'name': 'Bengaluru, Karnataka, India', 'latitude': 12.97, 'longitude': 77.59}


def test_opt_in_and_followup_routing():
    result = {'location': LOCATION, 'normalized_intent': {'activity': 'running', 'constraints': {'start': '2026-10-24T06:00:00+05:30'}}}
    previous = {**result, 'web_notices': {'status': 'found'}}
    assert not should_search(False, None, result, 'closures?')
    assert should_search(True, None, result, 'run')
    assert not should_search(True, previous, result, 'हिंदी में बताइए')
    assert not should_search(True, previous, result, 'Two hours later')
    assert should_search(True, previous, result, 'Any access restrictions?')
    assert should_search(True, result, result, 'Two hours later')  # First toggle-on turn.


def test_basic_search_cache_and_persistent_credit_limit(tmp_path):
    calls, events = [], []
    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        assert body['search_depth'] == 'basic' and body['auto_parameters'] is False
        assert body['max_results'] == 4 and body['include_answer'] is False
        assert 'asthma' not in body['query']
        return httpx.Response(200, json={'results': [
            {'title': 'Notice', 'url': 'https://bbmp.gov.in/notice', 'content': 'Check access', 'published_date': '2026-10-22'},
            {'title': 'Unsafe', 'url': 'javascript:alert(1)'},
            {'title': 'Unofficial', 'url': 'https://example.com/closure'},
        ]})
    cfg = Settings(database=str(tmp_path / 'cache'), tavily_api_key='test-key', web_search_daily_limit=1)
    async def emit(*args): events.append(args)
    async def run():
        service = Notices(cfg, httpx.MockTransport(handler))
        first = await service.search(LOCATION, 'running', '2026-10-24', emit)
        cached = await service.search(LOCATION, 'running', '2026-10-24', emit)
        limited = await Notices(cfg, httpx.MockTransport(handler)).search(LOCATION, 'cycling', '2026-10-24', emit)
        assert first['status'] == 'found' and len(first['results']) == 1
        assert first['results'][0]['published_at'] == '2026-10-22'
        assert cached['cache'] and limited['status'] == 'credit_limit'
        assert 'does not establish' in first['uncertainty']
    asyncio.run(run())
    assert len(calls) == 1
    assert events[0][0] == 'web_search' and events[1][0] == 'web_search_cache'


def test_failure_and_empty_results_do_not_claim_open(tmp_path):
    cfg = Settings(database=str(tmp_path / 'cache'), tavily_api_key='test-key')
    async def emit(*_): pass
    async def run():
        broken = Notices(cfg, httpx.MockTransport(lambda _: httpx.Response(401, text='secret-provider-error')))
        failed = await broken.search(LOCATION, 'running', '2026-10-24', emit)
        assert failed['status'] == 'unavailable'
        assert 'secret' not in json.dumps(failed)
        empty = Notices(cfg, httpx.MockTransport(lambda _: httpx.Response(200, json={'results': []})))
        result = await empty.search(LOCATION, 'cycling', '2026-10-24', emit)
        assert result['status'] == 'no_notices' and not result['results']
        assert 'does not establish' in result['uncertainty']
    asyncio.run(run())


def test_unconfigured_and_zero_budget_make_no_request(tmp_path):
    def forbidden(_): raise AssertionError('Network should not be called')
    async def emit(*_): pass
    async def run():
        for key, limit, status in [('', 10, 'unconfigured'), ('test-key', 0, 'credit_limit')]:
            cfg = Settings(database=str(tmp_path / 'cache'), tavily_api_key=key, web_search_daily_limit=limit)
            assert (await Notices(cfg, httpx.MockTransport(forbidden)).search(LOCATION, 'running', '2026-10-24', emit))['status'] == status
    asyncio.run(run())
