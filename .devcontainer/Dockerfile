FROM mcr.microsoft.com/devcontainers/base:ubuntu

RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-21-jre-headless \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /home/vscode/.cache/uv /home/vscode/.bun/install/cache \
    && chown -R vscode:vscode /home/vscode/.cache /home/vscode/.bun
