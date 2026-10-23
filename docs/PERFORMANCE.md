# GeoLens performance and cost

23 October 2026. No additional production inference was invoked to produce this report. Modal billing/configuration reads do not invoke the model.

## Recorded production measurements

| Measurement | Observed result | Meaning |
| --- | --- | --- |
| Cold model intent request | 57.464 s | Actual POST with startup retries, followed by complete JSON; 62 generated tokens. Includes queue/startup/network/generation. |
| Warm Hindi model intent request | 1.125 s | Complete structured interpretation, 77 generated tokens, thinking off. |
| Warm complete Lonavala API request | 2.596 s | Location, real venues, fresh/cached forecasts, scoring and comparative reasoning. |
| Warm relative-time follow-up | 2.014 s | Same location/activity, two hours later. |
| Warm Hindi follow-up | 1.810 s | Same location/activity/window, changed output language. |
| Ten Bengaluru activity queries | 1.828–6.243 s | All HTTP 200, genuine venues and forecasts; three to eight venues. |
| Production HTTP TTFB | Not separately captured | These archived calls measured full response latency. |
| Production first generated token | Not measured | Model and recommendation responses were buffered JSON, not token streams. |
| Idle scale-down window | 300 s configured | About five minutes after the last active input, then eligible to terminate. Not an observed exact shutdown duration. |
| Minimum / maximum replicas | 0 / 1 | No continuously reserved warm replica. |

The interface shows actual tool stages while waiting. Its first visible status message is not the first generated answer token. Cold startup cannot be separated from prefill or decoding using these archived full-response measurements. No invented first-token estimate is reported. These samples do not establish p95 or capacity under sustained load.

Sources: `modal-inference-verification.json`, `deployed-live.json`, `deployed-activities.json`. Read-only Modal autoscaler inspection reconfirmed the 300-second setting, minimum zero, maximum one and buffer zero. The earlier 60-second experiment was reverted.

## Current localhost

Website: http://localhost:5173. API: http://127.0.0.1:8000/docs. Qwen runs locally at http://127.0.0.1:8081 with no hosted inference credentials. The running local API was explicitly launched with the local URL, blank served alias and blank model API/proxy credentials. No Modal fallback is configured.

Fresh real-data running query: HTTP 200, no suitable option under the current conservative policy. Headers, first body bytes and complete JSON arrived at approximately 15.606 seconds. This buffered endpoint sends its answer after analysis finishes; it does not stream answer tokens. See `local-final-verification.json`. Local CPU model inference took 9.369 seconds within that request.

Local inference does not consume Modal GPU credits. Weather/map services still receive ordinary source requests. Enabling Web can consume a Tavily basic-search credit on a cache miss; leaving Web off makes no Tavily request. The real local Tavily smoke returned four official-domain results and is recorded separately.

## Resource and spending controls

The production VPS hosts only the lightweight API and static website for this application. Observed working set after prior live queries: API 198 MiB, Nginx 4.2 MiB. Caps: 512 MiB / 0.4 CPU and 48 MiB / 0.1 CPU respectively. These observations are not peak-resource guarantees.

The existing Modal endpoint uses an A100 40 GB, four requested CPU cores and 16 GiB requested memory. The latest read-only billing summary reported $1.38003773 metered usage and $0 billed after credits/allowances. These are account summary values, can lag and are not attributed solely to this last test. Previously verified account controls: $5 gross usage cap and $0 net-spending limit. No paid plan or spending-limit increase was made.

For a rough baseline estimate, Modal's published rates are $0.000583/s for A100 40 GB, $0.0000131/core/s and $0.00000222/GiB/s. At the requested resources this totals approximately $0.00067092/s, or $2.42 per active hour, before region premiums, higher actual usage or other applicable endpoint tariffs. A five-minute warm idle tail alone is approximately $0.20 at that baseline. A 57.5-second cold response plus five idle minutes is approximately $0.24. These are illustrative calculations, not a quote or measured charge per query.

Loading, processing and the configured warm idle period are billable; scaling to zero ends container compute charges. Requests during the warm period reset activity and avoid another cold start, but can extend billable uptime. The endpoint is in a selected European region, so the effective account rate may exceed the baseline. Use actual provider billing to reconcile costs. Source: https://modal.com/pricing (checked 23 October 2026).

Production was left running as previously authorized; new Tavily/contrast changes are local/source-only for review. No fresh production latency benchmark was run after the request to conserve resources.
