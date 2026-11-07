FROM python:3.13-alpine

RUN adduser -D user

WORKDIR /opt/rdgen

# Copy as the runtime user so it can chmod the entrypoint and create the data
# dir. Plain `COPY . .` leaves files owned by root, which the unprivileged user
# cannot write to.
COPY --chown=user:user . .
RUN chmod +x entrypoint.sh

USER user

RUN pip install --no-cache-dir -r requirements.txt \
 && mkdir -p /opt/rdgen/data/exe /opt/rdgen/data/png

# Data root for db.sqlite3, exe/ and png/. Mounted as a volume so builds and run
# records survive container restarts; the old image baked an empty db.sqlite3 at
# build time and lost everything on recreate.
ENV DATA_ROOT=/opt/rdgen/data
VOLUME ["/opt/rdgen/data"]

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD wget --spider 0.0.0.0:8000

# Migrations now run at container start (entrypoint.sh), not at build time, so
# they execute against the mounted volume.
ENTRYPOINT ["/opt/rdgen/entrypoint.sh"]
