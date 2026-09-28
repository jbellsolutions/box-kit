FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir . && useradd --system --home /data databox && mkdir -p /data && chown databox /data
# Listens on all interfaces INSIDE the container; compose publishes it on the host's loopback only.
ENV DATABOX_HOST=0.0.0.0 DATABOX_PORT=8092 DATABOX_STATE_DIR=/data
USER databox
VOLUME /data
EXPOSE 8092
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8092/health',timeout=4).status==200 else 1)"
CMD ["data-box", "serve"]
