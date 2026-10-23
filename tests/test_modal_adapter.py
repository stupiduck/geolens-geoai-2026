import asyncio
import json
import httpx
from geolens.config import settings
from geolens.model import LocalModel


def test_dedicated_endpoint_retries_original_request_during_startup(monkeypatch):
    calls=[]
    monkeypatch.setattr(settings,'model_served_id','geolens-qwen35-2b')
    monkeypatch.setattr(settings,'model_startup_grace_seconds',10)
    async def no_delay(_):pass
    monkeypatch.setattr(asyncio,'sleep',no_delay)
    async def response(request):
        calls.append(json.loads(request.content))
        if len(calls)==1:return httpx.Response(503,json={'error':'no upstreams available'})
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':'{"activity":"hiking"}'}}]})
    async def run():
        adapter=LocalModel()
        await adapter.client.aclose()
        adapter.client=httpx.AsyncClient(transport=httpx.MockTransport(response))
        result,_=await adapter.generate('Return intent','A hike near Lonavala',{'type':'object'},30)
        await adapter.client.aclose()
        assert result['activity']=='hiking'
    asyncio.run(run())
    assert len(calls)==2
    assert calls[0]==calls[1]
    assert calls[0]['model']=='geolens-qwen35-2b'
    assert calls[0]['chat_template_kwargs']['enable_thinking'] is False
