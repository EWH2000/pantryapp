# pantryapp production image.
# Rootless-friendly: runs as a non-root user, serves uvicorn directly
# (no --reload). Built with: podman build -t pantryapp .
FROM docker.io/library/python:3.14-slim

# Non-root user inside the container. Rootless Podman already isolates us
# from the host; running as a non-root UID in the image is defense in depth.
RUN useradd --create-home --uid 10001 app

WORKDIR /app

# Install dependencies in their own layer FIRST, so that editing app code
# doesn't invalidate the (slow) pip-install layer on every rebuild.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code.
COPY app/ ./app/

# Data directory for the mounted volume, owned by the app user. The live
# SQLite file lands here (see PANTRY_DB_PATH below).
RUN mkdir -p /data && chown app:app /data

USER app
ENV PANTRY_DB_PATH=/data/pantry.db
EXPOSE 8000

# Note: the liveness check is defined in the Quadlet unit (HealthCmd=),
# not here — an image-level HEALTHCHECK is ignored by Podman's default OCI
# image format.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
