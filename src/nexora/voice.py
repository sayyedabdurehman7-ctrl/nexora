"""Explicit local push-to-talk capture and pauseable memory-only audio playback."""

import asyncio
import io
import threading
import wave

from nexora.core import Conflict
from nexora.speech import FasterWhisperSTT, Pyttsx3TTS, SpeechError


class Recorder:
    rate = 16000

    def __init__(self, max_seconds=60):
        self.limit = max_seconds * self.rate * 2
        self.buffer = bytearray()
        self.lock = threading.Lock()
        self.stream = None

    def start(self):
        import sounddevice as sd

        def capture(data, frames, timing, status):
            with self.lock:
                remaining = self.limit - len(self.buffer)
                if remaining <= 0:
                    raise sd.CallbackStop
                self.buffer.extend(bytes(data)[:remaining])

        self.buffer.clear()
        try:
            self.stream = sd.RawInputStream(samplerate=self.rate, channels=1, dtype="int16", callback=capture)
            self.stream.start()
        except Exception:
            self.discard()
            raise SpeechError(
                "Microphone unavailable. Allow microphone access for desktop apps in Windows Settings, "
                "connect an input device, and close other apps using it."
            ) from None

    def test_permission(self) -> None:
        import sounddevice as sd

        try:
            sd.check_input_settings(samplerate=self.rate, channels=1, dtype="int16")
        except Exception:
            raise SpeechError(
                "Microphone unavailable. Allow microphone access for desktop apps in Windows Settings."
            ) from None

    def stop(self) -> bytes:
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        with self.lock:
            raw = bytes(self.buffer)
            self.buffer.clear()
        if len(raw) < self.rate // 5:
            raise SpeechError("Recording was too short. Press the microphone and speak, then stop.")
        out = io.BytesIO()
        with wave.open(out, "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(self.rate)
            writer.writeframes(raw)
        return out.getvalue()

    def discard(self):
        if self.stream:
            self.stream.abort()
            self.stream.close()
            self.stream = None
        with self.lock:
            self.buffer.clear()


class Playback:
    def __init__(self):
        self.stream = None
        self.data = b""
        self.position = 0
        self.state = "idle"

    def play(self, wav: bytes):
        import sounddevice as sd

        self.stop()
        with wave.open(io.BytesIO(wav), "rb") as reader:
            if reader.getsampwidth() != 2 or reader.getnchannels() not in (1, 2):
                raise SpeechError("Speech provider returned an unsupported WAV format.")
            channels, rate = reader.getnchannels(), reader.getframerate()
            self.data = reader.readframes(reader.getnframes())
        self.position, self.state = 0, "playing"

        def output(buffer, frames, timing, status):
            count = frames * channels * 2
            if self.state == "paused":
                buffer[:] = b"\0" * count
                return
            chunk = self.data[self.position : self.position + count]
            buffer[:] = chunk + b"\0" * (count - len(chunk))
            self.position += len(chunk)
            if self.position >= len(self.data):
                self.data = b""
                self.state = "idle"
                raise sd.CallbackStop

        try:
            self.stream = sd.RawOutputStream(samplerate=rate, channels=channels, dtype="int16", callback=output)
            self.stream.start()
        except Exception:
            self.stop()
            raise SpeechError("Speaker unavailable. Check the Windows output device and volume.") from None

    def pause(self):
        if self.state == "playing":
            self.state = "paused"
        elif self.state == "paused":
            self.state = "playing"

    def stop(self):
        if self.stream:
            self.stream.abort()
            self.stream.close()
            self.stream = None
        self.data, self.position, self.state = b"", 0, "idle"


class VoiceService:
    def __init__(self, settings, recorder=None, playback=None, stt=None, tts=None):
        self.settings = settings
        self.recorder = recorder or Recorder(settings.max_recording_seconds)
        self.playback = playback or Playback()
        self.stt, self.tts = stt, tts
        self.phase, self.transcript, self.error = "idle", "", ""
        self.job = None
        self.timer = None
        self.muted = False
        self.generation = 0
        self.capture_pending = False
        self.microphone_permission = "Not tested"
        self.listening = False

    def status(self):
        return {
            "phase": self.phase,
            "transcript": self.transcript,
            "error": self.error,
            "playback": self.playback.state,
            "muted": self.muted,
            "stt_provider": self.settings.stt_provider,
            "tts_provider": self.settings.tts_provider,
            "voice_mode": self.settings.voice_mode,
            "assistant_voice_enabled": self.settings.assistant_voice_enabled,
            "wake_phrase": self.settings.wake_phrase,
            "microphone_permission": self.microphone_permission,
            "microphone_active": self.phase in {"starting", "recording", "transcribing"} or self.listening,
            "wake_word_status": "Experimental - setup required",
        }

    def configure(self, mode: str, assistant_voice_enabled: bool, wake_phrase: str):
        if mode not in {"off", "push_to_talk", "wake_word"}:
            raise Conflict("Choose Off, Push-to-Talk, or Wake Word.")
        self.settings.voice_mode = mode
        self.settings.assistant_voice_enabled = assistant_voice_enabled
        self.settings.wake_phrase = wake_phrase.strip()[:40] or "Hey NEXORA"
        if mode != "wake_word":
            self.listening = False
        return self.status()

    async def test_microphone(self):
        checker = getattr(self.recorder, "test_permission", None)
        try:
            if checker:
                await asyncio.to_thread(checker)
            self.microphone_permission = "Allowed"
        except SpeechError:
            self.microphone_permission = "Blocked"
        except Exception:
            self.microphone_permission = "Unavailable"
        return self.status()

    async def start(self):
        if self.settings.voice_mode == "off":
            raise Conflict("Choose Push-to-Talk in Voice Settings first.")
        if self.settings.voice_mode == "wake_word":
            raise Conflict("Wake Word is experimental and requires additional setup. Use Push-to-Talk.")
        if self.capture_pending or self.phase in {"starting", "recording", "transcribing"}:
            raise Conflict("Finish or cancel the current recording first.")
        await self.cancel()
        self.phase, self.transcript, self.error = "starting", "", ""
        generation = self.generation
        self.capture_pending = True
        try:
            await asyncio.to_thread(self.recorder.start)
            if generation != self.generation:
                self.recorder.discard()
                return self.status()
            self.phase = "recording"
            self.timer = asyncio.create_task(self._limit())
        except SpeechError as exc:
            self.phase, self.error = "error", str(exc)
        except Exception:
            self.phase, self.error = (
                "error",
                "Microphone could not start. Check installed sounddevice and Windows microphone permissions.",
            )
        finally:
            self.capture_pending = False
        return self.status()

    async def _limit(self):
        await asyncio.sleep(self.settings.max_recording_seconds)
        if self.phase == "recording":
            await self.stop_recording()

    async def stop_recording(self):
        if self.phase != "recording":
            raise Conflict("The microphone is not recording.")
        self.phase = "transcribing"
        generation = self.generation
        if self.timer and self.timer != asyncio.current_task():
            self.timer.cancel()
        try:
            audio = await asyncio.to_thread(self.recorder.stop)
            if generation != self.generation:
                return self.status()
            self.job = asyncio.create_task(self._transcribe(audio))
        except SpeechError as exc:
            self.phase, self.error = "error", str(exc)
        return self.status()

    def providers(self):
        config = self.settings
        stt = self.stt or FasterWhisperSTT(config.whisper_model)
        tts = self.tts or Pyttsx3TTS(config.voice_name)
        return stt, tts

    async def _transcribe(self, audio: bytes):
        try:
            stt, _ = self.providers()
            self.transcript = (await stt.transcribe(audio)).strip()[:2000]
            if not self.transcript:
                raise SpeechError("No speech detected. Try recording again in a quieter place.")
            self.phase = "ready"
        except asyncio.CancelledError:
            self.phase, self.transcript = "idle", ""
        except SpeechError as exc:
            self.phase, self.error = "error", str(exc)
        except Exception:
            self.phase, self.error = "error", "Transcription failed. Check the speech service and microphone."

    async def speak(self, text: str):
        if self.muted:
            raise Conflict("Voice is muted. Unmute to play a response.")
        if self.phase in {"recording", "starting", "transcribing"}:
            raise Conflict("Finish recording before playing a response.")
        await self.cancel()
        self.phase, self.error = "synthesizing", ""
        self.job = asyncio.create_task(self._synthesize(text[:4000]))
        return self.status()

    async def _synthesize(self, text):
        try:
            _, tts = self.providers()
            audio = await tts.synthesize(text)
            if not self.muted:
                self.playback.play(audio)
            self.phase = "idle"
        except asyncio.CancelledError:
            self.phase = "idle"
        except SpeechError as exc:
            self.phase, self.error = "error", str(exc)
        except Exception:
            self.phase, self.error = "error", "Speech response failed. Check the voice service and speaker."

    async def cancel(self):
        self.generation += 1
        if self.timer and self.timer != asyncio.current_task():
            self.timer.cancel()
        if self.job and not self.job.done():
            self.job.cancel()
            await asyncio.gather(self.job, return_exceptions=True)
        self.recorder.discard()
        self.playback.stop()
        self.phase, self.transcript, self.error, self.listening = "idle", "", "", False
        return self.status()
