from dataclasses import dataclass


@dataclass
class AudioChunk:
    pcm16_bytes: bytes


class ASRAdapter:
    def transcribe(self, audio: AudioChunk) -> str:
        raise NotImplementedError


class TTSAdapter:
    def synthesize(self, text: str) -> AudioChunk:
        raise NotImplementedError


class NullASRAdapter(ASRAdapter):
    def transcribe(self, audio: AudioChunk) -> str:
        raise RuntimeError("No ASR provider configured")


class NullTTSAdapter(TTSAdapter):
    def synthesize(self, text: str) -> AudioChunk:
        raise RuntimeError("No TTS provider configured")
