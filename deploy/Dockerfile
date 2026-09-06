FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:99 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=UTC

# Install base packages, Python 3, and system utilities
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        wget \
        ca-certificates \
        python3 \
        python3-pip \
        python3-venv \
        xvfb \
        tzdata && \
    ln -fs /usr/share/zoneinfo/UTC /etc/localtime && \
    dpkg-reconfigure --frontend noninteractive tzdata && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Architecture-aware setup: If x86_64 (amd64), install Wine; if ARM64, install build tools
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then \
        echo "Configuring Wine for x86_64 (amd64)..." && \
        dpkg --add-architecture i386 && \
        apt-get update && \
        apt-get install -y --no-install-recommends wine wine32 wine64 && \
        apt-get clean && rm -rf /var/lib/apt/lists/* ; \
    else \
        echo "Configuring native environment for ARM64 ($ARCH)..." && \
        apt-get update && \
        apt-get install -y --no-install-recommends build-essential && \
        apt-get clean && rm -rf /var/lib/apt/lists/* ; \
    fi

WORKDIR /app

# Copy dependency specifications first to leverage Docker layer caching
COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application files
COPY . ./

# Ensure entrypoint and setup scripts have execute permissions
RUN chmod +x deploy/entrypoint.sh deploy/setup_oracle_swap.sh

ENTRYPOINT ["deploy/entrypoint.sh"]
