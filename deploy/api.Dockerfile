FROM python:3.11-slim
WORKDIR /app
COPY requirements.lock.txt /app/requirements.lock.txt
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY backend /app/backend
ENV PYTHONPATH=/app/backend
RUN useradd --uid 10001 --create-home geolens && mkdir /app/data && chown geolens:geolens /app/data
USER geolens
EXPOSE 8000
CMD ["uvicorn","geolens.app:app","--host","0.0.0.0","--port","8000","--workers","1","--limit-concurrency","12"]
