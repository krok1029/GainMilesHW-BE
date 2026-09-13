FROM python:3.13-slim-bookworm@sha256:ed86c82274b3c69b52fb5820f358f0bd7df0b603332063cb5c6e32bd220c3e6e AS dependencies

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir uv==0.6.16
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

FROM dependencies AS test
RUN uv sync --locked --no-install-project
COPY app ./app
COPY migrations ./migrations
COPY tests ./tests
CMD ["pytest", "-q"]

FROM dependencies AS runtime
RUN useradd --create-home --uid 10001 app
COPY app ./app
COPY migrations ./migrations
USER app
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "--error-logfile", "-", "app:create_app()"]
