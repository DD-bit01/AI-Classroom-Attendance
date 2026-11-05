# ==============================================================================
# AURA // AI Classroom Attendance - Hugging Face Spaces & Cloud Dockerfile
# ==============================================================================

FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=7860

# Install essential system dependencies for OpenCV and image operations
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set up standard Hugging Face non-root user (UID 1000)
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR /app

# Install Python packages
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir -U pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Switch to non-root user and pre-download Buffalo_L weights into /home/user/.insightface
USER user
RUN python -c "import insightface; insightface.app.FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])"

# Copy project files
COPY --chown=user:user . /app

# Ensure storage directories exist and are writable
USER root
RUN mkdir -p /app/student_photos /app/annotated_samples /app/models && \
    chown -R user:user /app /home/user
USER user

# Hugging Face Spaces default port
EXPOSE 7860

# Launch FastAPI app with Uvicorn
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-7860}"]
