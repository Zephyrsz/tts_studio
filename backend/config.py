from pathlib import Path
import json
import os

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
CONFIG = ROOT / 'config'
OUTPUTS = ROOT / 'outputs'
MAX_BODY = 22 * 1024 * 1024
MAX_CONCURRENCY = 10
DEFAULT_MODEL = 'google/gemini-3.8-flash-tts'
CLONE_MODEL = 'fish-audio/s2.1-pro'


def api_key() -> str:
    value = os.environ.get('OPENROUTER_API_KEY', '').strip()
    if value:
        return value
    env = ROOT / 'cfg.env'
    if env.is_file():
        for line in env.read_text(encoding='utf-8-sig').splitlines():
            name, sep, value = line.strip().removeprefix('export ').partition('=')
            if sep and name.strip() == 'OPENROUTER_API_KEY':
                return value.strip().strip('"\'')
    return ''


def model_catalog() -> list[dict]:
    return json.loads((CONFIG / 'models.json').read_text(encoding='utf-8'))
