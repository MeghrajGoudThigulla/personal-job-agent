# ==============================================================================
# Personal Job Agent - Dockerfile
# Optimized for Python 3.12 + XeLaTeX Compilation for Tailored Resumes + Render
# ==============================================================================

FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Install minimal OS dependencies and TeX Live XeLaTeX packages for PDF resume generation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    texlive-xetex \
    texlive-fonts-recommended \
    texlive-latex-extra \
    fonts-freefont-otf \
    fonts-dejavu \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY app/ ./app/
COPY data/ ./data/

# Ensure output directory for compiled resumes exists
RUN mkdir -p /app/data/tailored_resumes

# Expose Render default port
EXPOSE 8000

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Start the FastAPI application with Uvicorn
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
