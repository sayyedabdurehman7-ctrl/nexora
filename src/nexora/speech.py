"""Replaceable speech providers. Local workers are cancellable and hide raw errors."""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Protocol


class SpeechError(Exception):
    pass


class SpeechToTextProvider(Protocol):
    async def transcribe(self, wav: bytes) -> str: ...


class TextToSpeechProvider(Protocol):
    async def synthesize(self, text: str) -> bytes: ...


async def worker(mode: str, args: list[str], payload: bytes, timeout: float = 180) -> bytes:
    command = (
        [sys.executable, "speech-worker", mode, *args]
        if getattr(sys, "frozen", False)
        else [sys.executable, "-m", "nexora.speech_worker", mode, *args]
    )
    process = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(payload), timeout=timeout)
        if process.returncode != 0:
            raise SpeechError("Local speech failed. Check installed voice packages, model download and system voices.")
        return output
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


class FasterWhisperSTT:
    def __init__(self, model: str):
        self.model = model

    async def transcribe(self, wav: bytes) -> str:
        output = await worker("stt", [self.model], wav, timeout=300)
        return json.loads(output.decode("utf-8"))["text"]


class Pyttsx3TTS:
    def __init__(self, voice: str = ""):
        self.voice = voice

    async def synthesize(self, text: str) -> bytes:
        # Parent owns temporary output so cancellation also removes it.
        with tempfile.TemporaryDirectory(prefix="nexora-speech-") as folder:
            path = Path(folder) / "speech.wav"
            await worker("tts", [str(path)], json.dumps({"text": text, "voice": self.voice}).encode())
            if not path.exists() or path.stat().st_size < 44:
                raise SpeechError("Your system voice returned no audio. Select an installed voice in Settings.")
            return path.read_bytes()
