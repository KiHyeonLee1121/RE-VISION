FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[api]"
COPY configs ./configs
RUN useradd --create-home --uid 10001 revision && mkdir outputs && chown revision:revision outputs
USER revision
# Demo container. Live USB/serial mapping and a real model require a separate device setup.
CMD ["python", "-m", "revision", "demo", "--scenario", "scratch"]
