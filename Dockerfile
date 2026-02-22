FROM python:3.12-slim

# ── System deps + Tailscale ──────────────────────────────────
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git curl ca-certificates iptables iproute2 \
    && curl -fsSL https://tailscale.com/install.sh | sh \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python deps (cached layer — only rebuilds when requirements change) ──
COPY requirements.txt requirements2.txt* ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && if [ -f requirements2.txt ]; then pip install --no-cache-dir -r requirements2.txt; fi

# ── Application code ─────────────────────────────────────────
COPY . .

# ── Runtime directories ──────────────────────────────────────
RUN mkdir -p /var/run/tailscale /var/lib/tailscale \
        /app/data /app/memory /app/logs /app/knowledge

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]
