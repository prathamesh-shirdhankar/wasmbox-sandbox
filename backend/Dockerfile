
FROM python:3.12-slim

WORKDIR /code

COPY backend/requirements.txt .

RUN python -m pip install --no-cache-dir --retries 10 --timeout 120 -r requirements.txt

COPY backend/ .

COPY plugins/ /plugins

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
