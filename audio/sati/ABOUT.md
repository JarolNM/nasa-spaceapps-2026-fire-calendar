# Sati's voice — AI-generated audio

AI-generated speech: Microsoft neural text-to-speech (en-US-JennyNeural) via edge-tts; text drafted with AI assistance (Anthropic Claude). GeoElectronic, NASA Space Apps 2026.

Each MP3 is named by the djb2 hash (base 36) of its text (see `textos.json`) and carries this statement in its ID3 tags (TIT2, TPE1, COMM, TXXX ai_generated=true). Generated with `pipeline/voz_sati.py`.
