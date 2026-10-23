# Production deployment

Domain: https://geo.setuconsultants.in
Code: https://github.com/stupiduck/geolens-geoai-2026
Model: https://huggingface.co/manavmodi/geolens-geoai-2026

The dedicated `/opt/geolens` Compose project contains only FastAPI and static Nginx. Images are built locally and transferred to the VPS. Qwen runs on the existing Modal endpoint. The API binds no public host port; Nginx joins the existing attachable proxy network through application-specific Traefik labels. Global proxy configuration and existing applications are unchanged.

Resource caps: API 512 MiB / 0.4 CPU; web 48 MiB / 0.1 CPU. Production environment is a mode-600 file, injected into the API service with `env_file`. Geographic extracts are mounted separately; cache storage belongs to UID 10001. Never publish the environment file or image-transfer archives.

## Rollback

From `/opt/geolens`, run `docker compose down` to remove only GeoLens containers and its private network. Do not use `-v`, pruning or global service commands. The external proxy network and existing services remain intact. For subsequent releases, retain the previous GeoLens image tags and environment configuration before recreating this project.

## Release

Build `deploy/api.Dockerfile` and `deploy/web.Dockerfile` locally, transfer the image archive and completed OSM extracts, then run `docker compose up -d --no-build` in the dedicated directory using `deploy/production.compose.yaml` as its `compose.yaml`. The runtime model name is the dedicated endpoint alias; the base-model identity and revision remain separately documented.

The gateway limits analysis submissions to ten per minute per source address, with a short burst allowance. Polling and SSE are separate from this limit. Body size is capped at 16 KiB, API concurrency at three, and requests at 145 seconds including model readiness. Inference POST requests handle bounded cold-start retries; health checks use `/healthz` and do not invoke inference.

Modal caps verified in its billing dashboard on 23 October 2026: gross usage $5, net spending $0. Existing endpoint autoscaling is minimum zero, maximum one, buffer zero, idle scale-down 300 seconds. Billing estimates can lag; consult the provider account for authoritative totals. No always-on replicas or additional GPU service are created.

The Compose project is managed from `/opt/geolens` over SSH and is not registered as a Dokploy Project. Its containers use the existing Dokploy proxy network. No duplicate application has been created through Dokploy.

Latest optional Tavily and contrast source changes are held locally for user review. They have not been deployed to production. Production still serves the previously verified core. Heavy image builds occur locally; the last backend correction used a tiny source-only COPY layer on the VPS with no network or dependency installation.
