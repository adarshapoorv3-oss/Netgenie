FROM python:3.11-slim
WORKDIR /app
COPY services/guardrails/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services/common ./services/common
COPY services/guardrails ./services/guardrails
RUN touch services/__init__.py
ENV PYTHONPATH=/app
EXPOSE 6001
CMD ["uvicorn", "services.guardrails.app:app", "--host", "0.0.0.0", "--port", "6001"]
