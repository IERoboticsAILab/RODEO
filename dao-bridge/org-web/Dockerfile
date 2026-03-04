# build frontend
FROM node:20 AS frontend_build
WORKDIR /frontend
COPY web/package*.json ./
RUN npm ci
COPY web/ .
RUN npm run build

# runtime with node + python + nginx + supervisor
FROM node:20-slim AS runtime
WORKDIR /

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV=/opt/venv

# Install system packages, including venv
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    nginx \
    supervisor \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create venv and upgrade pip inside it
RUN python3 -m venv $VIRTUAL_ENV && $VIRTUAL_ENV/bin/pip install --upgrade pip
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Backend
WORKDIR /app
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY backend/ /app/

# Frontend runtime files
WORKDIR /web
COPY --from=frontend_build /frontend/.next /web/.next
COPY --from=frontend_build /frontend/package*.json /web/
COPY --from=frontend_build /frontend/node_modules /web/node_modules
COPY --from=frontend_build /frontend/next.config.js /web/

# Nginx and Supervisor configs
COPY nginx.conf /etc/nginx/nginx.conf
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD curl -fsS http://127.0.0.1/ || exit 1
CMD ["/usr/bin/supervisord","-c","/etc/supervisor/conf.d/supervisord.conf"]