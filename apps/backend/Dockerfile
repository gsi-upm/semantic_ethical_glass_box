FROM python:3.10-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.6.12 /uv /uvx /bin/

LABEL org.opencontainers.image.source=https://github.com/gsi-upm/semantic_ethical_glass_box
LABEL org.opencontainers.image.description="AMOR-SEGB server"
LABEL org.opencontainers.image.authors="Grupo de Sistemas Inteligentes - Universidad Politécnica de Madrid"
LABEL org.opencontainers.image.documentation="https://semantic-ethical-black-box-segb.readthedocs.io/en/stable/"
LABEL org.opencontainers.image.licenses=Apache-2.0

EXPOSE 5000

WORKDIR /app

ADD uv.lock uv.lock
ADD pyproject.toml pyproject.toml

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo
ENV PATH=/usr/local/cargo/bin:${PATH}

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | \
    sh -s -- -y --profile minimal --default-toolchain 1.75.0

RUN uv sync --frozen

ARG PROJECT="segb"
ADD ./apps/backend/api_info/${PROJECT}/api_info.json api_info.json
ADD ./apps/backend/api_info/${PROJECT}/api_description.md api_description.md

RUN mkdir /logs

COPY ./apps/backend/src /app/src
COPY ./apps/backend/static /app/static

CMD ["uv", "run", "uvicorn", "--app-dir", "/app/src", "main:app", "--host", "0.0.0.0", "--port", "5000", "--lifespan", "on"]
