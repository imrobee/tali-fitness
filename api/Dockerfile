# Same Python as the pinned Airflow image (apache/airflow:3.3.2 ships 3.13).
FROM python:3.13-slim

# No .pyc files in the bind-mounted source; print logs immediately.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dev image: test tools are included so `make test` runs inside this container.
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

COPY . .

EXPOSE 8000
# --factory: Uvicorn calls create_app(), which runs the startup guards first.
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
