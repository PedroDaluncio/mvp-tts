import asyncio
import unittest
import wave
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
import soundfile as sf

from backend.edge_pt_br import _decode_wav, synthesize


class EdgeSpeechTests(unittest.TestCase):
    def test_edge_mp3_becomes_a_pcm_wav(self):
        samples = 0.4 * np.sin(2 * np.pi * 440 * np.arange(4800) / 24000)
        encoded = BytesIO()
        sf.write(encoded, samples, 24000, format="MP3")
        mp3 = encoded.getvalue()

        async def save(path):
            Path(path).write_bytes(mp3)

        with patch("backend.edge_pt_br.edge_tts.Communicate") as communicate:
            communicate.return_value.save = save
            audio = asyncio.run(synthesize(" Olá ", "pt-BR-AntonioNeural"))
            communicate.assert_called_once_with("Olá", "pt-BR-AntonioNeural")

        with wave.open(BytesIO(audio)) as wav:
            self.assertEqual((wav.getframerate(), wav.getnchannels(), wav.getsampwidth()), (24000, 1, 2))
            pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
            self.assertEqual(len(pcm), len(samples))
            self.assertGreater(pcm.max(), 1000)

    def test_decode_failure_reports_the_ffmpeg_error(self):
        with TemporaryDirectory() as directory:
            mp3 = Path(directory) / "invalid.mp3"
            mp3.write_bytes(b"Invalid audio")
            with self.assertRaisesRegex(RuntimeError, "FFmpeg could not decode"):
                asyncio.run(_decode_wav(mp3, Path(directory) / "speech.wav"))

    def test_invalid_input_is_rejected_locally(self):
        with patch("backend.edge_pt_br.edge_tts.Communicate") as communicate:
            for text, voice in [(" ", "pt-BR-FranciscaNeural"), ("Oi", "pf_dora")]:
                with self.assertRaises(ValueError):
                    asyncio.run(synthesize(text, voice))
            communicate.assert_not_called()
