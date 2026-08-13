"""Speech-to-text integration boundaries."""

from typing import Protocol


class SpeechToTextProvider(Protocol):
    """Replaceable speech-to-text provider contract."""

    async def transcribe(self, audio: bytes, *, content_type: str) -> str:
        """Transcribe audio bytes to text."""


__all__ = ["SpeechToTextProvider"]
