FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ANONYMIZED_TELEMETRY=false BROWSER_USE_CLOUD_SYNC=false
WORKDIR /app

# requirements.lock when it exists (frozen from a build of requirements.txt), else the top-level pins.
COPY requirements.txt requirements.lock* ./
RUN pip install --no-cache-dir -r "$( [ -f requirements.lock ] && echo requirements.lock || echo requirements.txt )"

COPY server.py runner.py ./

# No browser here: the agent drives the hosted browser the gateway opened for the task, over CDP. A task runs as a child process
# that is killed at its timeout; its HOME and TMPDIR are a throwaway directory per task.
RUN useradd --create-home --shell /usr/sbin/nologin agent && chown -R agent:agent /app
USER agent

EXPOSE 3120
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:3120/api/health',timeout=8).status==200 else 1)"
CMD ["python", "server.py"]
