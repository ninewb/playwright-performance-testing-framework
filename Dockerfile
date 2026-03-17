# =======================================================
# Stage 1: Base System Tools
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
# Stage 3: Python + Playwright
# =======================================================
FROM azurecli AS playwright
WORKDIR /app

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

RUN apt-get update && apt-get install -y --no-install-recommends \
    jq rsync unzip zip git moreutils net-tools ssh vim python3 python3-pip python3.11-venv \
    coreutils watch gnupg2 wget vim curl libpq-dev clang bsdmainutils bc ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Copy tooling from build stages
COPY --from=playwright /usr/local/bin/kubectl   /usr/local/bin/
COPY --from=playwright /usr/local/bin/kustomize /usr/local/bin/
COPY --from=playwright /usr/local/bin/yq        /usr/local/bin/
COPY --from=playwright /usr/bin/az              /usr/bin/az
COPY --from=playwright /app/venv                /app/venv

WORKDIR /app

# Framework source — test files are injected at runtime via py-pw-loc-configmap
COPY framework.py       .
COPY common_enhanced.py .
COPY utils.py           .
COPY requirements.txt   .

ENV VIRTUAL_ENV=/app/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

ENTRYPOINT ["/bin/sleep", "infinity"]
