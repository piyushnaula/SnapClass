# One image for the API, the worker and the scheduler (different start commands).

# ---------- Stage 1: build (has compilers, not shipped) ----------
FROM python:3.11-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

# CPU-only PyTorch (much smaller than the default GPU build). Needed by Resemblyzer.
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt requirements-dev.txt ./
ARG INSTALL_DEV=false
RUN pip install -r requirements.txt \
    && if [ "$INSTALL_DEV" = "true" ]; then pip install -r requirements-dev.txt; fi

# OpenCV face models (Apache-2.0) from the official OpenCV model zoo.
RUN mkdir -p /models \
    && curl -fsSL -o /models/face_detection_yunet_2023mar.onnx \
       https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx \
    && curl -fsSL -o /models/face_recognition_sface_2021dec.onnx \
       https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx

# ---------- Stage 2: runtime (small, non-root) ----------
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH=/opt/venv/bin:$PATH
# ffmpeg decodes browser audio recordings (webm/ogg) for the voice pipeline.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY --from=builder /models /app/models
RUN useradd --create-home --uid 1000 app && mkdir -p /data/media && chown -R app:app /data /app
COPY --chown=app:app . .

USER app
EXPOSE 8000
CMD ["uvicorn", "snapclass.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
