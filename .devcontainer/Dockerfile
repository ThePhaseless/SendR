FROM mcr.microsoft.com/devcontainers/base:2.0.5-ubuntu-24.04

RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub \
    | gpg --dearmor -o /usr/share/keyrings/google-linux-signing-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-linux-signing-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
    > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/vscode/.cache/uv /home/vscode/.bun/install/cache \
    && chown -R vscode:vscode /home/vscode/.cache /home/vscode/.bun
