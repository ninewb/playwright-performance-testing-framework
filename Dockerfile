FROM ubuntu:latest as baseline
USER root

RUN apt-get update && apt-get upgrade -y \
  && apt install -y jq rsync unzip zip git moreutils net-tools ssh vim python3 python3-pip python3.12-venv coreutils watch \
  gnupg2 wget vim curl libpq-dev clang bsdmainutils bc

# install kubectl
RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
  && mv kubectl /usr/local/bin/ \
  && chmod a+x /usr/local/bin/kubectl 

# install kustomize
RUN curl -s "https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh" | bash \
  && mv kustomize /usr/local/bin/ \
  && chmod a+x /usr/local/bin/kustomize

# install yq
RUN wget -qO /usr/local/bin/yq https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 \
  && chmod a+x /usr/local/bin/yq

# install azure cli
RUN curl -sL https://aka.ms/InstallAzureCLIDeb | bash

COPY . /app/
WORKDIR /app

ENV VIRTUAL_ENV=/app/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN pip install --upgrade pip
RUN pip install -r requirements.txt
RUN python -m playwright install-deps
RUN python -m playwright install

ENTRYPOINT ["/bin/sleep", "infinity"]


# =======================================================
# Stage 1: Base System Tools (lightweight Debian)
# =======================================================
FROM debian:bookworm-slim AS base
USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    jq rsync unzip zip git moreutils net-tools ssh vim python3 python3-pip python3.11-venv \
    coreutils watch gnupg2 wget curl libpq-dev clang bc ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# kubectl
RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
  && mv kubectl /usr/local/bin/ && chmod a+x /usr/local/bin/kubectl

# kustomize
RUN curl -s "https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh" | bash \
  && mv kustomize /usr/local/bin/ && chmod a+x /usr/local/bin/kustomize

# yq
RUN wget -qO /usr/local/bin/yq https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 \
  && chmod a+x /usr/local/bin/yq


# =======================================================
# Stage 2: Azure CLI
# =======================================================
FROM base AS azurecli
RUN curl -sL https://aka.ms/InstallAzureCLIDeb | bash


# =======================================================
# Stage 3: Playwright Setup
# =======================================================
FROM azurecli AS playwright
WORKDIR /app

# Copy requirements early for cache efficiency
COPY requirements.txt .
RUN python3 -m venv /app/venv && \
    /app/venv/bin/pip install --upgrade pip && \
    /app/venv/bin/pip install -r requirements.txt && \
    /app/venv/bin/python -m playwright install-deps && \
    /app/venv/bin/python -m playwright install


# =======================================================
# Stage 4: Final Runtime Image
# =======================================================
FROM debian:bookworm-slim AS runtime
USER root

# Install all required runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    jq rsync unzip zip git moreutils net-tools ssh vim python3 python3-pip python3.11-venv \
    coreutils watch gnupg2 wget vim curl libpq-dev clang bsdmainutils bc ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Copy only what’s needed from previous layers
COPY --from=playwright /usr/local/bin/kubectl /usr/local/bin/
COPY --from=playwright /usr/local/bin/kustomize /usr/local/bin/
COPY --from=playwright /usr/local/bin/yq /usr/local/bin/
COPY --from=playwright /usr/bin/az /usr/bin/az
COPY --from=playwright /app /app

WORKDIR /app
# Copy local workspace files into image (ensure .dockerignore is used to avoid copying unwanted files)
COPY . /app
ENV VIRTUAL_ENV=/app/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

ENTRYPOINT ["/bin/sleep", "infinity"]