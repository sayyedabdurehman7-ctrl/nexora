FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
ENV HOST=0.0.0.0
ENV NEXORA_ALLOWED_HOSTS=*
CMD ["sh", "-c", "uvicorn nexora.web_app:app --host 0.0.0.0 --port ${PORT:-10000}"]
