#!/bin/sh
set -e

# Generate config.toml with environment variables
cat > /config.toml << EOF
secret = "${MTG_SECRET}"
bind-to = "0.0.0.0:${MTG_BIND_PORT}"
concurrency = 8192
prefer-ip = "prefer-ipv6"

[network.timeout]
tcp = "5s"
http = "10s"
idle = "1m"

[stats.prometheus]
enabled = true
bind-to = "0.0.0.0:8080"
http-path = "/metrics"
EOF

echo "Generated MTG config:"
cat /config.toml

echo "Starting MTG proxy..."
exec mtg run /config.toml