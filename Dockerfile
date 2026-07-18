# Dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY . .
RUN pip install --no-cache-dir .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:${PORT:-8000}/health').status==200 else 1)" || exit 1

CMD ["sh", "-c", "uvicorn webui.app:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]
