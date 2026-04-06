# Docker image for ARIA.
# Builds a container with all dependencies installed.

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y gcc curl && rm -rf /var/lib/apt/lists/*

# Install CPU-only torch first so pgmpy doesn't pull in ~2 GB of CUDA wheels
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY dashboard/ ./dashboard/
COPY data/ ./data/

# Generate synthetic data (local only — skip MIMIC download).
# data/synthetic/ has no __init__.py, so use exec+namespace instead of import.
RUN python -c "\
ns={'__name__':'aria_build'}; \
exec(open('data/synthetic/generate.py').read(), ns); \
ns['generate_qc_dataset']()"

EXPOSE 8000

# Start the FastAPI app with uvicorn
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
