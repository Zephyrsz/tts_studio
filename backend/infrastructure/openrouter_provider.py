from __future__ import annotations

import base64
import tempfile
from pathlib import Path

from ..domain.models import SynthesisRequest
from .. import config

# This module is the only boundary that knows the OpenRouter wire format.
from .tts_engine import request_api, prepare_request, save_audio


class OpenRouterProvider:
    def synthesize(self, request: SynthesisRequest):
        with tempfile.TemporaryDirectory(prefix='tts-studio-') as temp:
            args = self._arguments(request, Path(temp))
            payload, output, output_format = prepare_request(args)
            content, headers = request_api('/audio/speech', request.options.timeout, payload, request.api_key)
            output.write_bytes(content)
            save_audio(content, headers, output, output_format, request.options.sample_rate)
            return output.read_bytes(), headers.get('Content-Type', 'audio/octet-stream'), headers.get('X-Generation-Id', '')

    def _arguments(self, request, directory):
        import argparse
        args = argparse.Namespace(mode=request.mode, model=request.model, voice=request.voice, text=request.text, text_file=None, instructions=request.options.instructions or None, reference_audio=None, reference_text=request.reference_text, reference_text_file=None, format=request.options.format, output=directory / ('audio.' + request.options.format), sample_rate=request.options.sample_rate, timeout=request.options.timeout)
        if request.reference_data:
            suffix = Path(request.reference_name or 'reference.wav').suffix.lower()
            args.reference_audio = directory / ('reference' + suffix)
            args.reference_audio.write_bytes(base64.b64decode(request.reference_data))
        return args
