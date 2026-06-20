#!/bin/sh
set -e

# Persist the session signing key in the data volume so it survives restarts
# and never needs to be baked into the image or supplied manually. Generated
# once on first boot; reused thereafter.
DATA_DIR="${CC_DATA_DIR:-/data}"
KEY_FILE="${CC_SECRET_KEY_FILE:-$DATA_DIR/secret.key}"

mkdir -p "$DATA_DIR"

if [ ! -s "$KEY_FILE" ]; then
    python -c "import secrets; print(secrets.token_hex(32))" > "$KEY_FILE"
    chmod 600 "$KEY_FILE"
    echo "Generated new session key at $KEY_FILE"
fi

export CC_SECRET_KEY_FILE="$KEY_FILE"

exec "$@"
