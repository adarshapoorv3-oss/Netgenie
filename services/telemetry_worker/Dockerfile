FROM python:3.11-slim
WORKDIR /app
COPY services/telemetry_worker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services/common ./services/common
COPY services/telemetry_worker ./services/telemetry_worker
COPY data ./data
RUN touch services/__init__.py
ENV PYTHONPATH=/app
EXPOSE 6003
CMD ["uvicorn", "services.telemetry_worker.app:app", "--host", "0.0.0.0", "--port", "6003"]
