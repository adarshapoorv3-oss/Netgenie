FROM python:3.11-slim
WORKDIR /app
COPY services/gateway/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services/common ./services/common
COPY services/gateway ./services/gateway
COPY ui ./ui
RUN touch services/__init__.py
ENV PYTHONPATH=/app
EXPOSE 9000
CMD ["uvicorn", "services.gateway.app:app", "--host", "0.0.0.0", "--port", "9000"]
