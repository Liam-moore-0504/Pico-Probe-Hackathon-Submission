FROM node:22-alpine AS frontend
WORKDIR /ui
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ORCHESTRA_ENV=production
ARG TARGETARCH
ARG DOCKER_CLI_VERSION=29.1.3
ARG LEAN_VERSION=4.32.0
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl unzip \
    && case "$TARGETARCH" in amd64) docker_arch=x86_64; lean_arch=linux ;; arm64) docker_arch=aarch64; lean_arch=linux_aarch64 ;; *) echo "Unsupported architecture: $TARGETARCH" >&2; exit 1 ;; esac \
    && curl -fsSL "https://download.docker.com/linux/static/stable/${docker_arch}/docker-${DOCKER_CLI_VERSION}.tgz" \
      | tar -xz --strip-components=1 -C /usr/local/bin docker/docker \
    && chmod 0755 /usr/local/bin/docker \
    && curl -fsSL "https://github.com/leanprover/lean4/releases/download/v${LEAN_VERSION}/lean-${LEAN_VERSION}-${lean_arch}.zip" -o /tmp/lean.zip \
    && unzip -q /tmp/lean.zip -d /opt \
    && mv "/opt/lean-${LEAN_VERSION}-${lean_arch}" /opt/lean4 \
    && ln -s /opt/lean4/bin/lean /usr/local/bin/lean \
    && ln -s /opt/lean4/bin/lake /usr/local/bin/lake \
    && rm /tmp/lean.zip \
    && apt-get purge -y --auto-remove curl unzip \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home orchestra
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY --from=frontend /ui/dist ./frontend/dist
RUN chown -R orchestra:orchestra /app
USER orchestra
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "orchestra.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
