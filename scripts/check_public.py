"""Offline, value-redacted public-release checks. Never prints credential values."""
from pathlib import Path
import hashlib
import json
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
BLOCK_DIRS = {'.runtime', '.venv', 'node_modules', '__pycache__', 'logs',
              'chat_history', 'backups', 'samples', 'live2d-models', 'models'}
BLOCK_NAMES = {'settings.json', 'runtime-location.json', 'facts.json',
               'bot_config.toml', 'model_config.toml', 'config.toml', 'conf.yaml',
               'local-config.json', 'model-config.json', 'voice_config.json'}
BLOCK_EXT = {'.wav', '.mp3', '.ogg', '.flac', '.sqlite3', '.sqlite', '.db',
             '.jsonl', '.log', '.safetensors', '.onnx', '.moc3', '.exe', '.dll'}
PATTERNS = {
    'api_key_prefix': re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}'),
    'github_token': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{24,}|github_pat_[A-Za-z0-9_]{30,})'),
    'aws_access_key': re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'private_key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
}


def main():
    findings = []
    scanned = 0
    for file in sorted(ROOT.rglob('*')):
        relative = file.relative_to(ROOT)
        if '.git' in relative.parts or not file.is_file():
            continue
        if file.is_symlink() or any(p in BLOCK_DIRS for p in relative.parts) or file.name in BLOCK_NAMES or file.suffix.lower() in BLOCK_EXT:
            findings.append({'path': relative.as_posix(), 'kind': 'private_or_generated_file'})
        if file.name.startswith('.env') and file.name != '.env.example':
            findings.append({'path': relative.as_posix(), 'kind': 'environment_file'})
        try:
            text = file.read_text(encoding='utf-8-sig')
        except UnicodeDecodeError:
            findings.append({'path': relative.as_posix(), 'kind': 'unreviewed_binary'})
            continue
        scanned += 1
        if relative.as_posix() != 'scripts/check_public.py':
            for category, pattern in PATTERNS.items():
                for match in pattern.finditer(text):
                    findings.append({'path': relative.as_posix(), 'kind': category,
                                     'line': text.count('\n', 0, match.start()) + 1})
    manifest_path = ROOT/'SOURCE_MANIFEST.json'
    if manifest_path.exists():
        for entry in json.loads(manifest_path.read_text(encoding='utf-8'))['files']:
            file = (ROOT/entry['path']).resolve()
            if not file.is_relative_to(ROOT.resolve()) or not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != entry['sha256']:
                findings.append({'path': entry['path'], 'kind': 'fingerprint_mismatch'})
    print(json.dumps({'scanned_files': scanned, 'findings': findings,
                      'network_requests': 0, 'model_calls': 0}, ensure_ascii=False, indent=2))
    return int(bool(findings))


if __name__ == '__main__':
    sys.exit(main())
