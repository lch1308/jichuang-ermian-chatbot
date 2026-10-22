"""角色本地声带。仅监听回环地址、使用本机令牌；跑团以后可复用同一 API。"""
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
import asyncio
import base64
import io
import json
import os
import secrets
import threading
import time

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field

from voice_style import select_style

ROOT = Path(__file__).resolve().parent
TOKEN_FILE = ROOT / ".runtime" / "access_token.txt"
TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
if not TOKEN_FILE.exists():
    TOKEN_FILE.write_text(secrets.token_urlsafe(32), encoding="utf-8")
TOKEN = TOKEN_FILE.read_text(encoding="utf-8").strip()


def read_config():
    config = json.loads((ROOT / "voice_config.json").read_text(encoding="utf-8"))
    if not 1 <= config["max_text_chars"] <= 500 or not 5 <= config["generation_timeout_seconds"] <= 180:
        raise ValueError("语音长度或超时配置超出允许范围")
    return config


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    context: dict[str, Any] = Field(default_factory=dict)
    request_id: str = Field(default_factory=lambda: secrets.token_hex(12), pattern=r"^[a-zA-Z0-9_-]{1,64}$")


class VoiceEngine:
    def __init__(self):
        self.model = None
        self.busy = asyncio.Lock()
        self.available = True
        self.cancel_event = None

    def load(self):
        import torch
        from qwen_tts import Qwen3TTSModel
        if not torch.cuda.is_available():
            raise RuntimeError("未检测到可用 CUDA；不会静默改用慢速 CPU")
        torch.set_num_threads(4)
        config = read_config()
        model_path = ROOT / config["model_path"]
        if not (model_path / "config.json").is_file():
            raise RuntimeError("官方语音模型尚未下载完整")
        self.model = Qwen3TTSModel.from_pretrained(
            str(model_path), device_map="cuda:0", dtype=torch.bfloat16, attn_implementation="sdpa")
        # 0.1.1 的外层封装没有向下传递 stopping_criteria。只包住本实例
        # 的真正生成函数，不修改安装包文件；让超时停止标记能实际生效。
        from transformers import StoppingCriteria, StoppingCriteriaList
        engine = self
        class StopWhenCancelled(StoppingCriteria):
            def __call__(self, input_ids, scores, **kwargs):
                return bool(engine.cancel_event and engine.cancel_event.is_set())
        original_generate = self.model.model.talker.generate
        def cancellable_generate(*args, **kwargs):
            kwargs['stopping_criteria'] = StoppingCriteriaList([StopWhenCancelled()])
            return original_generate(*args, **kwargs)
        self.model.model.talker.generate = cancellable_generate
        print("本地语音模型加载完成；声音预设：" + config["speaker"], flush=True)

    def generate(self, text, style, config, cancelled):
        import soundfile as sf
        import torch
        self.cancel_event = cancelled
        try:
            with torch.inference_mode():
                wavs, sample_rate = self.model.generate_custom_voice(
                    text=text, language=config["language"], speaker=config["speaker"],
                    instruct=style["instruct"], **self.generation_parameters(config),
                    non_streaming_mode=True)
        finally:
            self.cancel_event = None
        if cancelled.is_set():
            raise TimeoutError("本次语音生成已取消，丢弃剩余结果")
        output = io.BytesIO()
        sf.write(output, wavs[0], sample_rate, format="WAV", subtype="PCM_16")
        return output.getvalue(), len(wavs[0]) / sample_rate

    def generation_parameters(self, config):
        # 使用当前已加载模型自己的合并函数：配置值覆盖模型默认值，避免日志“猜参数”。
        return self.model._merge_generate_kwargs(max_new_tokens=config["max_new_tokens"])


engine = VoiceEngine()


@asynccontextmanager
async def lifespan(app):
    await asyncio.to_thread(engine.load)
    yield


app = FastAPI(title="角色本地语音", lifespan=lifespan)


def guard(request):
    if not request.client or request.client.host not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(403, "语音服务只接受本机调用")
    if request.headers.get("origin"):
        raise HTTPException(403, "请通过 Live2D 后台调用，不接受网页跨站调用")
    if not secrets.compare_digest(request.headers.get("x-moonbell-token", ""), TOKEN):
        raise HTTPException(403, "需要本机语音调用令牌")


@app.get("/health")
def health():
    return {"service": "moonbell-local-voice", "ready": engine.model is not None,
            "available": engine.available and not engine.busy.locked(), "speaker": read_config()["speaker"]}


@app.post("/synthesize")
async def synthesize(body: SpeechRequest, request: Request):
    guard(request)
    config = read_config()
    if len(body.text) > config["max_text_chars"]:
        raise HTTPException(422, "单次文字太长，请分句后再请求")
    if engine.busy.locked() or not engine.available:
        raise HTTPException(429, "语音模型正忙，请稍后重试；不会无限排队")
    style = select_style(body.context, config)
    started = time.monotonic()
    cancelled = threading.Event()
    async with engine.busy:
        task = asyncio.create_task(asyncio.to_thread(engine.generate, body.text, style, config, cancelled))
        async def disconnect_watch():
            while not task.done():
                if await request.is_disconnected():
                    cancelled.set()
                    return
                await asyncio.sleep(.25)
        watcher = asyncio.create_task(disconnect_watch())
        try:
            audio, duration = await asyncio.wait_for(asyncio.shield(task), config["generation_timeout_seconds"])
        except (TimeoutError, asyncio.CancelledError):
            cancelled.set()
            # Python 无法杀掉 GPU 线程：在停止标记生效前拒绝下一次并发生成。
            engine.available = False
            def finished(future):
                engine.available = True
                if not future.cancelled():
                    future.exception()
            task.add_done_callback(finished)
            raise HTTPException(504, "语音生成超时，已请求停止")
        finally:
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)
    elapsed = time.monotonic() - started
    metadata = dict(instruction=style["instruct"], speaker=config["speaker"], reason=style["reason"],
                    model=Path(config["model_path"]).name, language=config["language"],
                    non_streaming_mode=True, observation=config.get("observation", {}))
    try:
        metadata["generation"] = engine.generation_parameters(config)
    except Exception as error:
        # 参数观测失败需要明确报告，但不能丢弃已经成功生成的音频。
        metadata["parameter_status"] = "参数观测失败：" + type(error).__name__
        print(metadata["parameter_status"], flush=True)
    day = datetime.now().astimezone().strftime("%Y-%m-%d")
    logdir = ROOT / ".runtime" / "日志"
    logdir.mkdir(exist_ok=True)
    with (logdir / (day + ".txt")).open("a", encoding="utf-8") as output:
        output.write(f"时间：{datetime.now().astimezone():%Y-%m-%d %H:%M:%S}｜本地语音合成\n"
                     f"声音：{config['speaker']}｜语气：{style['label']}｜来源：{style['reason']}\n"
                     f"文字长度：{len(body.text)}字（诊断日志不另存聊天正文）\n"
                     f"耗时：{elapsed:.2f}秒｜音频：{duration:.2f}秒\n\n")
    return Response(audio, media_type="audio/wav", headers={
        "X-Voice-Seconds": f"{elapsed:.3f}", "X-Audio-Seconds": f"{duration:.3f}",
        "X-Voice-Style": style["key"], "X-Request-Id": body.request_id,
        # HTTP 头只能安全传 ASCII；编码的是实际传给声带的要求，不是声学测量。
        "X-Voice-Metadata": base64.b64encode(json.dumps(
            metadata, ensure_ascii=False).encode('utf-8')).decode('ascii')})


if __name__ == "__main__":
    os.environ["HF_HUB_OFFLINE"] = "1"
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=12394, log_level="info")
