from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


class StorageError(ValueError):
    pass


def create_batch_directory(root_value: str, timestamp: int, text: str) -> Path:
    if not isinstance(root_value, str) or not root_value.strip():
        raise StorageError('请填写本地保存目录。')
    root = Path(root_value.strip()).expanduser()
    if not root.is_absolute():
        raise StorageError('保存目录请使用绝对路径。')
    try:
        root.mkdir(parents=True, exist_ok=True)
        destination = root.resolve() / str(timestamp)
        destination.mkdir()
        (destination / 'text.txt').write_text(text, encoding='utf-8')
    except FileExistsError:
        raise StorageError('同名批次目录已存在，已有文件不会被覆盖。') from None
    except OSError as exc:
        raise StorageError(f'无法创建保存目录：{exc}') from None
    return destination


def save_audio(directory: Path, filename: str, content: bytes) -> Path:
    if not filename or Path(filename).name != filename or any(ord(c) < 32 for c in filename):
        raise StorageError('保存文件名无效。')
    target = directory / filename
    if target.exists() or target.is_symlink():
        raise StorageError('同名音频已存在，已有文件不会被覆盖。')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, prefix='.saving-', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
        os.link(temporary, target)
        return target
    except FileExistsError:
        raise StorageError('同名音频已存在，已有文件不会被覆盖。') from None
    except OSError as exc:
        raise StorageError(f'音频保存失败：{exc}') from None
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def save_state(directory: Path, batch: dict) -> None:
    safe = dict(batch)
    safe.pop('api_key', None)
    (directory / 'batch.json').write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding='utf-8')
