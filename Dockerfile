FROM python:3.11-slim

WORKDIR /app

# Install system deps + Node.js for frontend build
RUN apt-get update && apt-get install -y \
    libglib2.0-0 libsm6 libxext6 libxrender-dev libgl1 \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Build React frontend
COPY frontend/ ./frontend/
RUN cd frontend && npm install && npm run build

# Copy built frontend into static folder for FastAPI to serve
RUN mkdir -p static && cp -r frontend/dist/* static/

# Copy rest of app
COPY . .

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]