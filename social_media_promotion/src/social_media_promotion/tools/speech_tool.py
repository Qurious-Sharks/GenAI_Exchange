import os
from typing import Optional

try:
    from google.cloud import speech_v1p1beta1 as speech
    from google.cloud import translate_v2 as translate
except Exception:  # pragma: no cover - optional import for environments without GCP
    speech = None
    translate = None


LANG_TO_GOOGLE_CODE = {
    "English": "en-US",
    "Hindi": "hi-IN",
    "Tamil": "ta-IN",
    "Telugu": "te-IN",
    "Spanish": "es-ES",
    "Malayalam": "ml-IN",
}


def _get_google_language_code(language_ui: Optional[str]) -> str:
    if not language_ui:
        return "en-US"
    return LANG_TO_GOOGLE_CODE.get(language_ui, "en-US")


def transcribe_speech(audio_file_path: str, language: Optional[str] = None, translate_to_english: bool = True) -> str:
    """Transcribe a local audio file to text using Google Cloud Speech-to-Text. Optionally translate to English.

    Args:
        audio_file_path: Absolute or relative path to a local audio file (wav, mp3, m4a, flac, etc.).
        language: Optional UI language name (e.g., 'Hindi', 'Tamil'). Falls back to env LANGUAGE or en-US.
        translate_to_english: If True, detected text will be translated to English using Google Translate.

    Returns:
        Transcribed (and optionally translated) text. Returns error string on failure.
    """
    if speech is None:
        return "Error: google-cloud-speech is not installed or failed to import."

    if not audio_file_path or not os.path.exists(audio_file_path):
        return "Error: audio file not found."

    language_ui = language or os.getenv("language") or os.getenv("LANGUAGE")
    language_code = _get_google_language_code(language_ui)

    try:
        client = speech.SpeechClient()

        with open(audio_file_path, "rb") as f:
            content = f.read()

        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            language_code=language_code,
            enable_automatic_punctuation=True,
            model="latest_long",
            audio_channel_count=1,
        )

        response = client.recognize(config=config, audio=audio)
        transcripts = []
        for result in response.results:
            if result.alternatives:
                transcripts.append(result.alternatives[0].transcript)

        text = " ".join(transcripts) if transcripts else ""

        if translate_to_english and text:
            if translate is None:
                return "Error: google-cloud-translate is not installed."
            try:
                tclient = translate.Client()
                translated = tclient.translate(text, target_language="en")
                return translated.get("translatedText", text)
            except Exception as te:
                return f"Error during translation: {te}"

        return text
    except Exception as e:
        return f"Error during transcription: {e}"


