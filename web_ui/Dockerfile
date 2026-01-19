
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Cloud Run sets PORT env var, defaults to 8080)
ENV PORT=8080

# Run FastAPI
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT}
