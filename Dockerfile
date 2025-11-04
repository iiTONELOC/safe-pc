# Build the front end first then we don't need node in final image
FROM node:24.8 AS nodebuild
WORKDIR /app
COPY . /app
# Build frontend
WORKDIR /app/src/proxmox_auto_installer/front_end/tailwindcss
RUN npm ci || npm install && npm run build

# Build final container image
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PATH="/root/.local/bin:$PATH"


WORKDIR /app
COPY . /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cpio \
    curl \
    git \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    qemu-utils \
    rsync \
    squashfs-tools \
    tzdata \
    wget \
    xorriso \
    zstd && \
    rm -rf /var/lib/apt/lists/*

# Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Install python deps + build certs
RUN poetry config virtualenvs.create true \
 && poetry install --no-interaction --no-ansi \
 && poetry run gen-cert

# Copy built css from node build stage - currently thats all we do, no minification or anything is done
WORKDIR /app/src/proxmox_auto_installer/front_end/static/css
COPY --from=nodebuild /app/src/proxmox_auto_installer/front_end/static/css/tailwind.css ./tailwind.css

# Back to app root
WORKDIR /app

# persistent dirs for runtime data
RUN mkdir -p /app/certs /app/data/isos /app/data/cached_answers/data /app/dist /app/logs

VOLUME ["/app/certs", "/app/data", "/app/dist", "/app/logs"]

EXPOSE 33007 33008

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -skf https://127.0.0.1:33008/ || exit 1

CMD ["poetry", "run", "start"]
