FROM python:3.14.6-slim-bookworm

LABEL org.opencontainers.image.title="Post-Semantic Communication artifact"
LABEL org.opencontainers.image.version="arxiv24-v25.1.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=0 \
    MPLBACKEND=Agg \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8

WORKDIR /artifact

COPY requirements.lock .python-version RELEASE_VERSION ./
RUN python -m pip install --no-cache-dir --requirement requirements.lock

COPY . .

CMD ["python", "src/verify_artifacts.py", "--regenerate", "--run-validation"]
