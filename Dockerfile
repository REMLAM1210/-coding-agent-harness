# Dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY . .
RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "webui.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
