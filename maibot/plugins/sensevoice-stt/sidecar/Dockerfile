FROM python:3.12-slim

# ffmpeg 用于音频格式自动转换（SenseVoice 内部使用）
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# PyTorch CPU 版（funasr-onnx 底层仍依赖 torch）
RUN pip install --no-cache-dir --force-reinstall \
    torch==2.6.0+cpu torchaudio==2.6.0+cpu \
    --index-url https://download.pytorch.org/whl/cpu

# FunASR + API 依赖
RUN pip install --no-cache-dir -U \
    funasr \
    modelscope \
    fastapi \
    uvicorn[standard] \
    python-multipart \
    jieba \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com

ENV MODELSCOPE_CACHE=/models

COPY server.py /app/server.py
WORKDIR /app
EXPOSE 50000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "50000"]
