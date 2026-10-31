from __future__ import annotations

import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..domain.models import Batch, BatchRequest, SynthesisRequest, Task
from ..infrastructure import storage


class BatchManager:
    def __init__(self, provider, roots=None):
        self.provider = provider
        self.lock = threading.RLock()
        self.batches: dict[str, Batch] = {}
        self.executors: dict[str, ThreadPoolExecutor] = {}
        if roots:
            self._load_roots(roots)

    def create(self, request: BatchRequest) -> Batch:
        if request.mode == 'preset' and not request.voices:
            raise ValueError('请至少选择一种音色。')
        if not 1 <= request.concurrency <= 10:
            raise ValueError('并发度必须在 1–10 之间。')
        if type(request.timestamp) is not int or not 0 < request.timestamp < 10**16:
            raise ValueError('批次时间戳必须为有效的 Unix 秒数。')
        if not request.text.strip():
            raise ValueError('朗读文本不能为空。')
        if request.options.format not in {'wav', 'mp3', 'pcm'}:
            raise ValueError('输出格式仅支持 WAV、MP3、PCM。')
        prefix = request.filename_prefix or str(request.timestamp)
        if Path(prefix).name != prefix or any(ord(char) < 32 for char in prefix) or not prefix.strip():
            raise ValueError('自定义文件名前缀无效。')
        if any(Path(voice).name != voice or not voice.strip() for voice in request.voices):
            raise ValueError('音色名称无效。')
        directory = storage.create_batch_directory(request.directory, request.timestamp, request.text)
        batch_id = uuid.uuid4().hex
        tasks = [Task(id=uuid.uuid4().hex, voice=voice, filename=f'{prefix}-{voice}.{request.options.format}') for voice in request.voices]
        if request.mode == 'clone':
            tasks = [Task(id=uuid.uuid4().hex, voice='声音克隆', filename=f'{prefix}-声音克隆.{request.options.format}')]
        batch = Batch(id=batch_id, directory=str(directory), timestamp=request.timestamp, text=request.text, concurrency=request.concurrency, mode=request.mode, tasks=tasks, api_key=request.api_key, options=request.options, reference_data=request.reference_data, reference_name=request.reference_name, reference_text=request.reference_text)
        with self.lock:
            self.batches[batch_id] = batch
            self._persist(batch)
        executor = ThreadPoolExecutor(max_workers=min(request.concurrency, len(tasks) or 1), thread_name_prefix=f'tts-{batch_id[:6]}')
        self.executors[batch_id] = executor
        for task in tasks:
            executor.submit(self._run_task, batch, task, request)
        return batch

    def _run_task(self, batch: Batch, task: Task, request: BatchRequest):
        with self.lock:
            if batch.stop_requested:
                task.status = 'cancelled'; self._persist(batch); return
            task.status = 'running'; task.started_at = time.time(); self._persist(batch)
        try:
            synthesis = SynthesisRequest(mode=request.mode, model=request.options.model, text=request.text, voice=None if request.mode == 'clone' else task.voice, reference_data=request.reference_data, reference_name=request.reference_name, reference_text=request.reference_text, options=request.options, api_key=request.api_key)
            content, _, generation_id = self.provider.synthesize(synthesis)
            target = storage.save_audio(Path(batch.directory), task.filename, content)
            with self.lock:
                task.status = 'done'; task.size = len(content); task.saved_path = str(target); task.generation_id = generation_id; task.finished_at = time.time(); self._persist(batch)
        except Exception as exc:
            with self.lock:
                task.status = 'error'; task.error = str(exc); task.finished_at = time.time(); self._persist(batch)
        finally:
            self._finish_if_done(batch)

    def _finish_if_done(self, batch):
        with self.lock:
            if all(task.status in {'done', 'error', 'cancelled'} for task in batch.tasks):
                batch.status = 'stopped' if batch.stop_requested else 'completed'
                self._persist(batch)

    def stop(self, batch_id: str) -> bool:
        batch = self.get(batch_id)
        with self.lock:
            batch.stop_requested = True
            for task in batch.tasks:
                if task.status == 'pending': task.status = 'cancelled'
            self._persist(batch)
        self._finish_if_done(batch)
        return True

    def get(self, batch_id: str) -> Batch:
        with self.lock:
            if batch_id not in self.batches:
                raise KeyError('批次不存在。')
            return self.batches[batch_id]

    def wait(self, batch_id: str, timeout=10):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.get(batch_id).status in {'completed', 'stopped'}:
                return
            time.sleep(0.01)
        raise TimeoutError('批次等待超时。')

    def _persist(self, batch):
        storage.save_state(Path(batch.directory), batch.to_dict())

    def _load_roots(self, roots):
        for directory in roots:
            state = Path(directory) / 'batch.json'
            if not state.is_file():
                continue
            data = json.loads(state.read_text(encoding='utf-8'))
            tasks = [Task(**item) for item in data.get('tasks', [])]
            batch = Batch(id=data['id'], directory=data['directory'], timestamp=data['timestamp'], text=data.get('text', ''), concurrency=data.get('concurrency', 1), mode=data.get('mode', 'preset'), tasks=tasks, status=data.get('status', 'completed'), stop_requested=data.get('stop_requested', False), error=data.get('error', ''))
            self.batches[batch.id] = batch
