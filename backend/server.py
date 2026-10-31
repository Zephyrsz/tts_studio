from __future__ import annotations

import argparse
import json
import mimetypes
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from . import config
from .application.batch_service import BatchManager
from .domain.models import BatchRequest, SynthesisOptions
from .infrastructure.catalog import load_voices
from .infrastructure.openrouter_provider import OpenRouterProvider


class AppServer(ThreadingHTTPServer):
    allow_reuse_address = True


def choose_directory():
    if sys.platform != 'darwin':
        raise ValueError('当前系统请直接填写本地目录的绝对路径。')
    result = subprocess.run(['osascript', '-e', 'POSIX path of (choose folder with prompt "选择语音文件保存目录")'], capture_output=True, text=True, timeout=120)
    if result.returncode:
        if '-128' in result.stderr:
            return None
        raise ValueError('无法打开目录选择窗口。')
    return result.stdout.strip()


def make_server(port=8771):
    server = AppServer(('127.0.0.1', port), Handler)
    server.manager = BatchManager(OpenRouterProvider(), roots=list(config.OUTPUTS.glob('*')) if config.OUTPUTS.is_dir() else [])
    server.batch_lock = threading.Lock()
    return server


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False).encode('utf-8')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send_data(self, status, body, mime='application/json; charset=utf-8', headers=None):
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Access-Control-Allow-Origin', 'http://127.0.0.1:8770')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def respond(self, status, value):
        self.send_data(status, json_bytes(value))

    def do_OPTIONS(self):
        self.send_data(204, b'', 'text/plain')

    def do_GET(self):
        path = urlsplit(self.path).path
        try:
            if path == '/api/v1/config':
                self.respond(200, {'default_text': 'こんにちは。今日は日本語の音声合成をテストしています。自然で聞き取りやすい声でお話しします。', 'default_instructions': '自然な日本語で、発音を明瞭にし、落ち着いた会話の速さで読み上げてください。', 'preset_model': config.DEFAULT_MODEL, 'clone_model': config.CLONE_MODEL, 'voices': load_voices(config.DATA / 'voice_list.csv'), 'models': config.model_catalog(), 'output_directory': str(config.OUTPUTS), 'can_choose_directory': sys.platform == 'darwin'})
                return
            if path == '/api/v1/batches':
                self.respond(200, [batch.to_dict() for batch in self.server.manager.batches.values()])
                return
            if path.startswith('/api/v1/tasks/') and path.endswith('/audio'):
                return self.audio(path.split('/')[4])
            if path.startswith('/api/v1/batches/'):
                batch = self.server.manager.get(path.split('/')[4])
                self.respond(200, batch.to_dict())
                return
            self.respond(404, {'error': '接口不存在。'})
        except KeyError:
            self.respond(404, {'error': '批次不存在。'})
        except (OSError, ValueError, IndexError) as exc:
            self.respond(400, {'error': str(exc)})

    def do_POST(self):
        origin = self.headers.get('Origin')
        if origin and origin not in {'http://127.0.0.1:8770', 'http://localhost:8770'}:
            self.respond(403, {'error': '请从新的本地前端发起请求。'})
            return
        path = urlsplit(self.path).path
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= config.MAX_BODY:
                raise ValueError('请求为空或过大。')
            data = json.loads(self.rfile.read(length))
            if path == '/api/v1/directory-picker':
                self.respond(200, {'directory': choose_directory()}); return
            if path == '/api/v1/preview':
                self.respond(200, {'requests': self.preview_requests(data)}); return
            if path == '/api/v1/batches':
                batch = self.server.manager.create(self.to_batch_request(data))
                self.respond(202, batch.to_dict()); return
            if path.startswith('/api/v1/batches/') and path.endswith('/stop'):
                batch = self.server.manager.get(path.split('/')[4])
                self.server.manager.stop(batch.id)
                self.respond(200, batch.to_dict())
                return
            self.respond(404, {'error': '接口不存在。'})
        except json.JSONDecodeError:
            self.respond(400, {'error': '请求必须是 JSON。'})
        except KeyError:
            self.respond(404, {'error': '批次不存在。'})
        except (OSError, ValueError, TypeError, IndexError) as exc:
            self.respond(400, {'error': str(exc)})

    def to_batch_request(self, data):
        mode = data.get('mode', 'preset')
        if mode not in {'preset', 'clone'}:
            raise ValueError('合成模式无效。')
        text = str(data.get('text', '')).strip()
        voices = data.get('voices') or ([] if mode == 'clone' else [data.get('voice', '')])
        if not isinstance(voices, list) or any(not isinstance(v, str) or not v.strip() for v in voices):
            raise ValueError('音色选择无效。')
        options = SynthesisOptions(model=str(data.get('model') or (config.CLONE_MODEL if mode == 'clone' else config.DEFAULT_MODEL)), format=str(data.get('format') or ('mp3' if mode == 'clone' else 'wav')), sample_rate=int(data.get('sample_rate', 24000)), timeout=float(data.get('timeout', 120)), instructions=str(data.get('instructions') or ''))
        if not text:
            raise ValueError('朗读文本不能为空。')
        if type(data.get('timestamp')) is not int or not 0 < data['timestamp'] < 10**16:
            raise ValueError('批次时间戳必须为有效的 Unix 秒数。')
        if options.format not in {'wav', 'mp3', 'pcm'}:
            raise ValueError('输出格式仅支持 WAV、MP3、PCM。')
        if not 8000 <= options.sample_rate <= 192000 or options.timeout <= 0 or options.timeout > 600:
            raise ValueError('采样率或请求超时超出允许范围。')
        if mode == 'clone' and (not data.get('reference_data') or not data.get('reference_name')):
            raise ValueError('声音克隆需要参考录音。')
        return BatchRequest(directory=data.get('directory', ''), timestamp=data.get('timestamp'), text=text, voices=voices, concurrency=int(data.get('concurrency', 1)), filename_prefix=str(data.get('filename_prefix') or ''), options=options, api_key=str(data.get('api_key') or config.api_key()), mode=mode, reference_data=data.get('reference_data'), reference_name=data.get('reference_name'), reference_text=data.get('reference_text'))

    def preview_requests(self, data):
        mode = data.get('mode', 'preset')
        voices = data.get('voices') or [None]
        requests = []
        for voice in voices:
            item = {'model': data.get('model') or (config.CLONE_MODEL if mode == 'clone' else config.DEFAULT_MODEL), 'input': data.get('text', ''), 'response_format': data.get('format', 'wav')}
            if voice:
                item['voice'] = voice
            if mode == 'clone':
                item['input_references'] = '[参考录音已隐藏]'
            requests.append(item)
        return requests

    def audio(self, task_id):
        for batch in self.server.manager.batches.values():
            for task in batch.tasks:
                if task.id == task_id and task.status == 'done':
                    path = Path(task.saved_path)
                    body = path.read_bytes()
                    mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
                    self.send_data(200, body, mime, {'Content-Disposition': f'attachment; filename="{path.name}"'})
                    return
        self.respond(404, {'error': '音频不存在。'})


def main(argv=None):
    parser = argparse.ArgumentParser(description='TTS Studio separated backend')
    parser.add_argument('--port', type=int, default=8771)
    parser.add_argument('--open', action='store_true')
    args = parser.parse_args(argv)
    with make_server(args.port) as server:
        print(f'Backend API: http://127.0.0.1:{server.server_port}', flush=True)
        if args.open:
            webbrowser.open(f'http://127.0.0.1:{server.server_port}/api/v1/config')
        server.serve_forever()


if __name__ == '__main__':
    main()
