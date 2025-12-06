FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY data/ ./data/
COPY .env ./

# Create necessary directories
RUN mkdir -p logs vector_store

# Expose ports
EXPOSE 8000
EXPOSE 8501

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8000/health || exit 1

# Run the application
CMD ["sh", "-c", "uvicorn src.api.main:app --host 0.0.0.0 --port 8000 & streamlit run src/frontend/app.py --server.port 8501 --server.address 0.0.0.0"]