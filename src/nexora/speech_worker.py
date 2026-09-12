"""Private local worker: no raw audio files for STT and no logged user text."""

import io
import json
import sys


def main():
    mode = sys.argv[1]
    if mode == "stt":
        from faster_whisper import WhisperModel

        model = WhisperModel(sys.argv[2], device="cpu", compute_type="int8")
        segments, _ = model.transcribe(io.BytesIO(sys.stdin.buffer.read()), beam_size=1, vad_filter=True)
        result = " ".join(segment.text.strip() for segment in segments).strip()
        sys.stdout.buffer.write(json.dumps({"text": result}).encode("utf-8"))
    elif mode == "tts":
        import pyttsx3

        payload = json.loads(sys.stdin.buffer.read())
        engine = pyttsx3.init()
        if payload["voice"]:
            voices = engine.getProperty("voices")
            selected = next((v.id for v in voices if payload["voice"].lower() in (v.name + " " + v.id).lower()), None)
            if selected is None:
                raise ValueError("Voice not installed")
            engine.setProperty("voice", selected)
        engine.save_to_file(payload["text"], sys.argv[2])
        engine.runAndWait()
        engine.stop()


if __name__ == "__main__":
    main()
