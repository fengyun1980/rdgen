#!/bin/sh
# Runtime startup: prepare writable dirs, apply migrations against the mounted
# volume, then hand over to gunicorn.
#
# migrate used to run at image build time, which baked an empty db.sqlite3 into
# the image layer. With the data directory now mounted as a volume that build-time
# database is hidden, so migrations must run when the container starts.
set -e

DATA_DIR="${DATA_DIR:-/opt/rdgen/data}"

mkdir -p "$DATA_DIR" "$DATA_DIR/exe" "$DATA_DIR/png"

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Starting gunicorn..."
exec /home/user/.local/bin/gunicorn -c gunicorn.conf.py rdgen.wsgi:application
