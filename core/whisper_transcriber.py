import logging
import os
from config import settings

logger = logging.getLogger(__name__)

class LocalWhisperTranscriber:
    """Local Speech-to-Text transcriber using faster-whisper or openai-whisper."""

    def __init__(self, model_size: str = None, device: str = None):
        self.model_size = model_size or settings.WHISPER_MODEL_SIZE
        self.device = device or settings.WHISPER_DEVICE
        self._model = None

    def _load_model(self):
        """Lazy loader for Whisper model."""
        if self._model is not None:
            return self._model

        try:
            from faster_whisper import WhisperModel
            logger.info(f"Loading local faster-whisper model '{self.model_size}' on device '{self.device}'...")
            self._model = WhisperModel(self.model_size, device=self.device, compute_type="int8")
            self._engine = "faster_whisper"
        except Exception as e:
            logger.warning(f"Could not load faster-whisper ({e}). Trying openai-whisper fallback...")
            try:
                import whisper
                self._model = whisper.load_model(self.model_size)
                self._engine = "openai_whisper"
            except Exception as e_fallback:
                logger.error(f"Failed to load whisper engines: {e_fallback}")
                self._model = None
                self._engine = None

        return self._model

    def transcribe(self, audio_path: str) -> str:
        """Transcribe an audio file (OGG, OPUS, WAV, MP3) into text locally."""
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        model = self._load_model()
        if model is None:
            logger.warning("Whisper model unavailable. Returning fallback mock transcript.")
            return "[Whisper Error: Model not initialized. Please install faster-whisper or whisper.]"

        try:
            if self._engine == "faster_whisper":
                segments, info = model.transcribe(audio_path, beam_size=5)
                transcript_text = " ".join([segment.text for segment in segments]).strip()
                return transcript_text
            elif self._engine == "openai_whisper":
                result = model.transcribe(audio_path)
                return result.get("text", "").strip()
        except Exception as e:
            logger.error(f"Error transcribing audio file {audio_path}: {e}")
            return f"[Transcription error: {str(e)}]"

whisper_transcriber = LocalWhisperTranscriber()
