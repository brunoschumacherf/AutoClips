FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN --mount=type=bind,target=/src,readonly --mount=type=secret,id=package_ca \
    apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && if [ -f /run/secrets/package_ca ]; then export PIP_CERT=/run/secrets/package_ca; fi \
    && pip install -r /src/requirements.lock \
    && useradd --create-home --uid 10001 cortalives \
    && mkdir -p /data/media /data/huggingface /data/beat \
    && cp -a /src/. /app/ \
    && chown -R cortalives:cortalives /app /data
USER cortalives
ENV MEDIA_ROOT=/data/media HF_HOME=/data/huggingface
EXPOSE 8000
CMD ["uvicorn", "core.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
