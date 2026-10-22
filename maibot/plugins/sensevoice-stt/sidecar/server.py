"""SenseVoice STT API 服务 — FastAPI 包装 FunASR SenseVoiceSmall。

单一 endpoint ``POST /v1/audio/transcriptions``，接收 multipart/form-data
音频文件，返回 ``{"text": "..."}``。

模型首次加载时自动从 ModelScope 下载（约 1GB），缓存在 ``$MODELSCOPE_CACHE``。
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn.error")

app = FastAPI(title="SenseVoice STT", version="0.1.0")

model: AutoModel | None = None
TEMP_DIR = Path("/tmp/sensevoice")


@app.on_event("startup")
async def startup() -> None:
    """加载 SenseVoice-Small 模型（CPU）。

    如果 ``/models`` 目录已有缓存则秒起，否则自动从 ModelScope 下载。
    """
    global model
    model_cache = os.environ.get("MODELSCOPE_CACHE", "/models")
    logger.info(
        "加载 SenseVoiceSmall 模型 (cache=%s, device=cpu)...",
        model_cache,
    )

    loop = asyncio.get_running_loop()
    model = await loop.run_in_executor(
        None,
        lambda: AutoModel(model="iic/SenseVoiceSmall", device="cpu"),
    )
    logger.info("SenseVoiceSmall 模型加载完成")


@app.get("/health")
async def health() -> dict[str, str]:
    """健康检查端点。"""
    return {"status": "ready" if model is not None else "loading"}


@app.post("/v1/audio/transcriptions")
async def transcribe(
    file: UploadFile = File(...),
    language: str = Form("auto"),
) -> dict[str, str]:
    """语音转文字。

    Args:
        file: 音频文件（WAV/MP3/OGG/FLAC 等，SenseVoice 自动处理格式）。
        language: 语言标签，``auto`` 自动检测，也可指定 ``zh``/``en``/``yue``/``ja``/``ko``。

    Returns:
        ``{"text": "转录文本"}``。
    """
    if model is None:
        raise HTTPException(status_code=503, detail="模型尚未加载完成")

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = str(TEMP_DIR / f"{uuid.uuid4().hex}.wav")

    try:
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)

        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(
            None,
            lambda: model.generate(
                input=temp_path,
                cache={},
                language=language,
                use_itn=True,
                batch_size_s=60,
            ),
        )

        raw_text = ""
        if results:
            first = results[0]
            raw_text = first.get("text", "") if isinstance(first, dict) else str(first)
        text = rich_transcription_postprocess(raw_text).strip()
        logger.info("转录完成: text_length=%d", len(text))
        return {"text": text}

    except Exception as exc:
        logger.exception("转录失败")
        raise HTTPException(status_code=500, detail="转录失败") from exc

    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
