"""从官方固定版本下载模型，保留断点；不关闭 HTTPS 证书校验。"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time

import requests

ROOT = Path(__file__).resolve().parent
MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
REVISION = "0c0e3051f131929182e2c023b9537f8b1c68adfe"
DEST = ROOT / "models" / "Qwen3-TTS-12Hz-1.7B-CustomVoice"


def download(name):
    path = DEST / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    temporary = path.with_name(path.name + ".part")
    offset = temporary.stat().st_size if temporary.exists() else 0
    url = f"https://huggingface.co/{MODEL}/resolve/{REVISION}/{name}"
    headers = {"Range": f"bytes={offset}-"} if offset else {}
    with requests.get(url, headers=headers, stream=True, timeout=(20, 90)) as response:
        response.raise_for_status()
        if offset and response.status_code != 206:
            offset = 0  # 服务不支持断点时重新下载，不拼接成损坏文件。
        if offset and not response.headers.get("content-range", "").startswith(f"bytes {offset}-"):
            raise RuntimeError("服务返回错误的续传范围")
        length = response.headers.get("Content-Length")
        expected = int(length) + offset if length else None
        received, last_report = offset, time.monotonic()
        with temporary.open("ab" if offset else "wb") as output:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    output.write(chunk)
                    received += len(chunk)
                if time.monotonic() - last_report > 20:
                    progress = f"{received / expected:.0%}" if expected else "下载中"
                    print(f"{name}: {progress} ({received//1048576} MiB)", flush=True)
                    last_report = time.monotonic()
        if expected is not None and received != expected:
            raise RuntimeError("模型下载长度不一致")
    temporary.replace(path)
    print("下载完成：" + name, flush=True)


if __name__ == "__main__":
    response = requests.get(f"https://huggingface.co/api/models/{MODEL}/revision/{REVISION}", timeout=25)
    response.raise_for_status()
    files = [x["rfilename"] for x in response.json()["siblings"]
             if x["rfilename"].endswith((".json", ".txt", ".safetensors"))]
    with ThreadPoolExecutor(max_workers=3) as executor:
        list(executor.map(download, files))
    print("官方模型下载完成：" + REVISION, flush=True)
