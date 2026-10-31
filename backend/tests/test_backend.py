import base64
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.application.batch_service import BatchManager
from backend.domain.models import BatchRequest, SynthesisOptions
from backend.infrastructure.storage import StorageError
from backend.server import make_server


class FakeProvider:
    def __init__(self):
        self.active = 0
        self.maximum = 0
        self.calls = []
        self.lock = threading.Lock()

    def synthesize(self, request):
        with self.lock:
            self.active += 1
            self.maximum = max(self.maximum, self.active)
            self.calls.append(request.voice)
        try:
            time.sleep(0.015)
            if request.voice == 'Charon':
                raise RuntimeError('voice unavailable')
            return b'RIFF' + request.voice.encode(), 'audio/wav', f'gen-{request.voice}'
        finally:
            with self.lock:
                self.active -= 1


class BatchManagerTests(unittest.TestCase):
    def request(self, root, voices=('Zephyr', 'Puck', 'Kore', 'Orus'), concurrency=2):
        return BatchRequest(
            directory=str(root), timestamp=1793325000, text='こんにちは。', voices=list(voices),
            concurrency=concurrency, filename_prefix='', options=SynthesisOptions(), api_key='test-key'
        )

    def test_batch_saves_text_audio_and_isolates_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider = FakeProvider()
            manager = BatchManager(provider)
            batch = manager.create(self.request(tmp, voices=('Zephyr', 'Charon', 'Puck')))
            self.assertEqual(Path(batch.directory, 'text.txt').read_text(), 'こんにちは。')
            manager.wait(batch.id)
            current = manager.get(batch.id)
            self.assertEqual([task.status for task in current.tasks], ['done', 'error', 'done'])
            self.assertEqual(Path(batch.directory, '1793325000-Zephyr.wav').read_bytes(), b'RIFFZephyr')
            self.assertIn('voice unavailable', current.tasks[1].error)
            self.assertEqual(current.tasks[0].generation_id, 'gen-Zephyr')

    def test_parallelism_is_hard_limit_and_stop_cancels_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider = FakeProvider()
            manager = BatchManager(provider)
            request = self.request(tmp, voices=tuple(f'V{i}' for i in range(8)), concurrency=3)
            batch = manager.create(request)
            manager.wait(batch.id)
            self.assertLessEqual(provider.maximum, 3)
            self.assertEqual(len(provider.calls), 8)
            provider.calls.clear()
            second_request = self.request(tmp, voices=tuple(f'X{i}' for i in range(8)), concurrency=1)
            second_request = BatchRequest(**{**second_request.__dict__, 'timestamp': 1793325001})
            second = manager.create(second_request)
            self.assertTrue(manager.stop(second.id))
            manager.wait(second.id)
            self.assertEqual(sum(task.status == 'cancelled' for task in manager.get(second.id).tasks), 7)

    def test_same_timestamp_and_filename_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = BatchManager(FakeProvider())
            manager.create(self.request(tmp, voices=('Zephyr',)))
            with self.assertRaises(StorageError):
                manager.create(self.request(tmp, voices=('Puck',)))

    def test_manager_reloads_completed_batch_without_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider = FakeProvider()
            manager = BatchManager(provider)
            batch = manager.create(self.request(tmp, voices=('Zephyr',)))
            manager.wait(batch.id)
            reloaded = BatchManager(FakeProvider(), roots=[Path(tmp) / '1793325000'])
            self.assertEqual(reloaded.get(batch.id).tasks[0].status, 'done')
            self.assertNotIn('test-key', json.dumps(reloaded.get(batch.id).to_dict()))


class StorageAndApiTests(unittest.TestCase):
    def test_clone_request_contains_reference_without_voice(self):
        from backend.domain.models import SynthesisRequest
        request = SynthesisRequest(mode='clone', model='fish-audio/s2.1-pro', text='新しい文章。', voice=None, reference_data=base64.b64encode(b'RIFF').decode(), reference_name='sample.wav', reference_text='元の文章。', options=SynthesisOptions())
        self.assertIsNone(request.voice)
        self.assertEqual(request.reference_name, 'sample.wav')


if __name__ == '__main__':
    unittest.main()
