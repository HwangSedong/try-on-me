# Production-like runtime for benchmarks: the Lightsail release runs on Python 3.10.
# Build context is backend/ so that both versions share the same dependency set.
FROM python:3.10-slim
COPY requirements-prod.txt /tmp/requirements-prod.txt
RUN pip install --no-cache-dir -r /tmp/requirements-prod.txt
