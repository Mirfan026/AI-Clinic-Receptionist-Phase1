from __future__ import annotations

import os

from groq import Groq


DEFAULT_STT_MODEL = "whisper-large-v3-turbo"


class GroqVoiceService:
    """
    Groq speech-to-text service.

    This service ONLY converts voice audio into text.

    It does not:
    - access the database
    - check appointment availability
    - book appointments
    - provide medical advice

    The transcription is sent to the existing clinic agent,
    where normal safety, routing, RAG, and tools are applied.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:

        self.api_key = (
            api_key
            or os.getenv("GROQ_API_KEY")
        )

        if not self.api_key:
            raise RuntimeError(
                "GROQ_API_KEY was not found."
            )

        self.model = (
            model
            or os.getenv("GROQ_STT_MODEL")
            or DEFAULT_STT_MODEL
        )

        self.client = Groq(
            api_key=self.api_key
        )

    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "clinic_voice.wav",
    ) -> str:
        """
        Convert microphone WAV audio into text.

        Language is not forced so Whisper can automatically
        recognize English, Urdu, Roman Urdu, or mixed speech.
        """

        if not audio_bytes:
            raise ValueError(
                "No audio data was provided."
            )

        transcription = (
            self.client.audio.transcriptions.create(
                file=(
                    filename,
                    audio_bytes,
                ),
                model=self.model,
                response_format="json",
                temperature=0.0,
                prompt=(
                    "Maple Crescent Family Clinic. "
                    "The speaker may use English, Urdu, "
                    "Roman Urdu, or mixed language. "
                    "Doctor names may include Dr. Amina Rahman, "
                    "Dr. Bilal Hassan, Dr. Hamza Qureshi, "
                    "Dr. Nadia Ahmed, and Dr. Sara Malik."
                ),
            )
        )

        text = getattr(
            transcription,
            "text",
            "",
        )

        if not text:
            raise RuntimeError(
                "Groq returned an empty transcription."
            )

        text = str(text).strip()

        if not text:
            raise RuntimeError(
                "Groq returned an empty transcription."
            )

        return text