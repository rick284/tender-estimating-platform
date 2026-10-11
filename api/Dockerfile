# Build from the repository root:  docker build -f api/Dockerfile .
FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ENV=production
WORKDIR /app
COPY api/requirements.txt /app/api/requirements.txt
RUN pip install --no-cache-dir -r /app/api/requirements.txt
COPY engine/tender_engine /app/engine/tender_engine
COPY api/*.py /app/api/
RUN useradd --create-home --uid 10001 appuser
USER appuser
WORKDIR /app/api
EXPOSE 10000
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000} --proxy-headers --forwarded-allow-ips='*'"]
