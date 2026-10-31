import csv
from pathlib import Path


def load_voices(path: Path) -> list[dict[str, str]]:
    voices = []
    seen = set()
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        row = next(csv.reader([line])) if ',' in line else line.split(None, 1)
        voice = row[0].strip()
        if voice.lower() in {'voice', 'voice_id', 'id', 'name', '音色', '音色名称'} or voice in seen:
            continue
        seen.add(voice)
        voices.append({'id': voice, 'description': row[1].strip() if len(row) > 1 else ''})
    if not voices:
        raise ValueError('voice_list.csv 中没有可用音色。')
    return voices
