FROM python:3.11-slim
WORKDIR /app
COPY services/retrieval_worker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services/common ./services/common
COPY services/retrieval_worker ./services/retrieval_worker
COPY data ./data
RUN touch services/__init__.py
ENV PYTHONPATH=/app
EXPOSE 6002
CMD ["uvicorn", "services.retrieval_worker.app:app", "--host", "0.0.0.0", "--port", "6002"]
