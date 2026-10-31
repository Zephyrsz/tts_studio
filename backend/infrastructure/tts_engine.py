"""Provider-side request construction and audio validation, independent of HTTP routes."""
from pathlib import Path
import base64
import json
import os
import tempfile
import urllib.error
import urllib.request
import wave

BASE_URL = 'https://openrouter.ai/api/v1'
GEMINI_VOICES = {'Zephyr': '明亮', 'Puck': '活泼', 'Charon': '播报感', 'Kore': '坚定', 'Fenrir': '有活力', 'Leda': '年轻', 'Orus': '沉稳', 'Aoede': '轻快', 'Callirrhoe': '随和', 'Autonoe': '明亮', 'Enceladus': '气声', 'Iapetus': '清晰', 'Umbriel': '随和', 'Algieba': '平滑', 'Despina': '柔和', 'Erinome': '清晰', 'Algenib': '沙哑', 'Rasalgethi': '播报感', 'Laomedeia': '活泼', 'Achernar': '柔和', 'Alnilam': '坚定', 'Schedar': '平稳', 'Gacrux': '成熟', 'Pulcherrima': '直率', 'Achird': '友好', 'Zubenelgenubi': '休闲', 'Vindemiatrix': '温柔', 'Sadachbia': '生动', 'Sadaltager': '睿智', 'Sulafat': '温暖'}


def request_api(path, timeout, payload=None, api_key=None):
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
    headers = {'Accept': 'application/json' if payload is None else 'audio/*'}
    if body is not None: headers['Content-Type'] = 'application/json'
    if api_key: headers['Authorization'] = f'Bearer {api_key}'
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE_URL + path, data=body, headers=headers), timeout=timeout) as response:
            return response.read(), response.headers
    except urllib.error.HTTPError as exc:
        message = exc.read(8192).decode(errors='replace')
        if api_key: message = message.replace(api_key, '[REDACTED]')
        raise ValueError(f'OpenRouter HTTP {exc.code}: {message[:1200]}') from None


def prepare_request(args):
    mode = args.mode or ('clone' if args.reference_audio else 'preset')
    model = args.model or ('fish-audio/s2.1-pro' if mode == 'clone' else 'google/gemini-3.8-flash-tts')
    gemini = model.startswith('google/gemini-')
    if mode == 'clone' and (not args.reference_audio or args.voice or gemini): raise ValueError('克隆模式需要兼容的参考录音模型，且不能指定预设音色。')
    if mode == 'preset' and args.reference_audio: raise ValueError('预设模式不能携带参考录音。')
    output_format = args.format or ('wav' if gemini else 'mp3')
    if gemini and output_format == 'mp3': raise ValueError('Gemini 仅支持 WAV 或 PCM。')
    text = (args.text or '').strip()
    if not text: raise ValueError('朗读文本不能为空。')
    payload = {'model': model, 'input': text, 'response_format': 'pcm' if output_format == 'wav' else output_format}
    if mode == 'preset':
        voice = args.voice or 'Zephyr'
        payload['voice'] = next((item for item in GEMINI_VOICES if item.lower() == voice.lower()), voice)
    else:
        suffix = Path(args.reference_audio).suffix.lower(); mime = {'wav': 'audio/wav', '.wav': 'audio/wav', '.mp3': 'audio/mpeg'}.get(suffix)
        payload['input_references'] = [{'type': 'input_audio', 'input_audio': {'data': f'data:{mime};base64,{base64.b64encode(Path(args.reference_audio).read_bytes()).decode()}'}}]
        if args.reference_text: payload['input_references'].append({'type': 'text', 'text': args.reference_text})
    if args.instructions: payload['instructions'] = args.instructions
    return payload, Path(args.output), output_format


def save_audio(content, headers, output, output_format, sample_rate):
    mime = headers.get('Content-Type', '').split(';', 1)[0].lower()
    if not content or (output_format != 'mp3' and len(content) % 2): raise ValueError('接口返回空音频或不完整 PCM。')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as handle:
        temporary = Path(handle.name)
        if output_format == 'wav':
            with wave.open(handle, 'wb') as wav:
                wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(sample_rate); wav.writeframes(content)
        else: handle.write(content)
    os.replace(temporary, output)
