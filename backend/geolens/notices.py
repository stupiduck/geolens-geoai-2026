"""Optional notices, separate from environmental measurements and eligibility.

One basic request per cache miss, no retries. Reservations survive restarts and
count failed requests conservatively because the provider may have billed them.
"""
import asyncio
import hashlib
import json
import re
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .config import settings

UNCERTAINTY = 'Search notices may be incomplete or outdated. No matching notice does not establish that a venue is open. Confirm access with the venue or authority.'
NOTICE_CUES = re.compile(r'clos(?:ed|ure|ing)|restrict|advis|notice|event|access|open(?:ing)?|बंद|प्रतिबंध|प्रवेश|आयोजन|चेतावनी', re.I)


def should_search(enabled, previous, result, question):
    if not enabled or not result.get('location'):
        return False
    if not previous or not previous.get('web_notices') or NOTICE_CUES.search(question):
        return True
    old, new = previous.get('location', {}), result['location']
    if any(old.get(k) != new.get(k) for k in ('latitude', 'longitude')):
        return True
    a, b = previous.get('normalized_intent', {}), result['normalized_intent']
    return a.get('activity') != b.get('activity') or str(a.get('constraints', {}).get('start', ''))[:10] != str(b.get('constraints', {}).get('start', ''))[:10]


class Notices:
    def __init__(self, config=settings, transport=None):
        self.config, self.transport = config, transport
        self.lock = asyncio.Lock()

    @contextmanager
    def database(self):
        path = Path(self.config.database + '.notices')
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path, timeout=2)
        db.execute('CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, expires REAL, value TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS budget (period TEXT PRIMARY KEY, requests INTEGER NOT NULL)')
        try:
            with db:
                yield db
        finally:
            db.close()

    async def search(self, location, activity, day, emit):
        base = {'provider': 'Tavily', 'results': [], 'uncertainty': UNCERTAINTY, 'cache': False, 'requested': True}
        if not self.config.tavily_api_key.get_secret_value():
            return {**base, 'status': 'unconfigured'}
        # Query uses the resolved area only, never the user's personal profile.
        area = re.sub(r'[\x00-\x1f]', ' ', location['name'])[:180]
        query = f'{area} {activity.replace("_", " ")} official closure access restrictions events advisory {day}'[:399]
        key = hashlib.sha256(f'{location["latitude"]:.3f}|{location["longitude"]:.3f}|{activity}|{day}'.encode()).hexdigest()
        try:
            async with asyncio.timeout(self.config.web_search_timeout + 1):
                async with self.lock:
                    return await self._search(base, key, query, emit)
        except (TimeoutError, sqlite3.Error, OSError):
            return {**base, 'status': 'unavailable'}

    async def _search(self, base, key, query, emit):
        now = datetime.now(timezone.utc)
        with self.database() as db:
            cached = db.execute('SELECT value FROM cache WHERE key=? AND expires>?', (key, time.time())).fetchone()
            if cached:
                await emit('web_search_cache', 'Reusing cached web notices')
                return {**json.loads(cached[0]), 'cache': True}
            # Atomic reservation also protects against multiple processes.
            db.execute('BEGIN IMMEDIATE')
            periods = [(now.strftime('%Y-%m-%d'), self.config.web_search_daily_limit), (now.strftime('%Y-%m'), self.config.web_search_monthly_limit)]
            for period, limit in periods:
                row = db.execute('SELECT requests FROM budget WHERE period=?', (period,)).fetchone()
                if (row[0] if row else 0) >= limit:
                    return {**base, 'status': 'credit_limit'}
            for period, _ in periods:
                db.execute('INSERT INTO budget VALUES (?,1) ON CONFLICT(period) DO UPDATE SET requests=requests+1', (period,))
            db.commit()
        await emit('web_search', 'Searching official local notices with Tavily')
        result = {**base, 'query': query, 'retrieved_at': now.isoformat(), 'status': 'unavailable'}
        try:
            async with httpx.AsyncClient(timeout=self.config.web_search_timeout, transport=self.transport) as client:
                response = await client.post('https://api.tavily.com/search', headers={'Authorization': 'Bearer ' + self.config.tavily_api_key.get_secret_value()}, json={
                    'query': query, 'search_depth': 'basic', 'auto_parameters': False,
                    'max_results': 4, 'topic': 'general', 'time_range': 'month',
                    'include_domains': ['gov.in', 'nic.in'],
                    'include_answer': False, 'include_raw_content': False, 'include_images': False, 'include_usage': True,
                })
                response.raise_for_status()
                payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get('results'), list):
                raise ValueError('Invalid search response')
            results = []
            for item in payload.get('results', [])[:4]:
                if not isinstance(item, dict):
                    continue
                parsed = urlparse(item.get('url', ''))
                host = (parsed.hostname or '').lower()
                if parsed.scheme not in ('https', 'http') or parsed.username or not any(host == d or host.endswith('.' + d) for d in ('gov.in', 'nic.in')):
                    continue
                results.append({'id': f'notice-{len(results)+1}', 'url': item['url'], 'title': str(item.get('title', host))[:300],
                    'snippet': str(item.get('content', ''))[:900], 'published_at': item.get('published_date') or None,
                    'source_type': 'official_domain', 'verification': 'search_excerpt_unverified'})
            result.update(status='found' if results else 'no_notices', results=results, credits_reserved=1)
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            pass  # Never expose provider errors, request headers or API keys.
        with self.database() as db:
            db.execute('DELETE FROM cache WHERE expires<?', (time.time(),))
            db.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?)', (key, time.time() + (3600 if result['status'] != 'unavailable' else 120), json.dumps(result)))
        return result


notices = Notices()
