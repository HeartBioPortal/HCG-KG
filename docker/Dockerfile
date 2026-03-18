FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md LICENSE /app/
COPY src /app/src
COPY configs /app/configs
COPY data/sample /app/data/sample

RUN pip install --upgrade pip && pip install -e .

ENTRYPOINT ["hcg-kg"]
