FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# mysqlclient is a C extension: it needs the MySQL client headers and a
# compiler at build time.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential pkg-config default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x entrypoint.sh

# Documentation only: the platform injects PORT and the entrypoint binds it.
EXPOSE 8000

# collectstatic, migrate and gunicorn all run from the entrypoint, where the
# service environment variables exist. See backend/entrypoint.sh.
CMD ["./entrypoint.sh"]
