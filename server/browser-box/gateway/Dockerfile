FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY gateway ./gateway

# No browser here on purpose: the browsers are hosted (Browser Use Cloud, Browserbase).
# /lane is a shared volume. Docker seeds a new volume from the image directory, so the
# ownership has to exist here or the unprivileged user cannot take the lock.
RUN useradd --create-home --shell /usr/sbin/nologin box \
 && mkdir -p /lane \
 && chown -R box:box /app /lane
USER box

EXPOSE 8080
CMD ["python", "-m", "gateway.server"]
