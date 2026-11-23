import unittest
import wave
from io import BytesIO
from struct import unpack
from unittest.mock import Mock, patch

import torch
from kokoro import KPipeline

from backend.kokoro_pt_br import MAX_PHONEMES, phoneme_chunks, synthesize


class LongNarrationTests(unittest.TestCase):
    def test_each_chunk_is_encoded_before_the_next_is_generated(self):
        pipeline = Mock()
        pipeline.g2p.return_value = ("ola", None)

        def generate(chunk, voice):
            samples = torch.tensor([0.5, -0.5])
            yield Mock(audio=samples)
            samples.fill_(0.25)
            yield Mock(audio=samples)

        pipeline.generate_from_tokens.side_effect = generate
        audio = synthesize("Olá", "pf_dora", pipeline=pipeline)
        with wave.open(BytesIO(audio)) as wav:
            self.assertEqual((wav.getframerate(), wav.getnchannels(), wav.getsampwidth()), (24000, 1, 2))
            self.assertEqual(wav.getnframes(), 4)
            self.assertEqual(unpack("<4h", wav.readframes(4)), (16384, -16384, 8192, 8192))

    def test_unpunctuated_paragraph_reaches_model_in_full(self):
        text = "o trem segue pelo interior do Brasil " * 30 + "até a última estação"
        pipeline = KPipeline(lang_code="p", repo_id="hexgrad/Kokoro-82M", model=False)
        expected, _ = pipeline.g2p(text)
        self.assertGreater(len(expected), MAX_PHONEMES)

        # Use the real Portuguese phonemizer and capture each model invocation.
        model = Mock(device="cpu")
        model.return_value.audio = torch.zeros(24)
        pipeline.model = model
        with (
            patch("backend.kokoro_pt_br.get_pipeline", return_value=pipeline),
            patch.object(pipeline, "load_voice", return_value=torch.zeros(MAX_PHONEMES, 1)),
        ):
            synthesize(text, "pf_dora")

        spoken = [call.args[0] for call in model.call_args_list]
        self.assertTrue(all(0 < len(chunk) <= MAX_PHONEMES for chunk in spoken))
        self.assertEqual(" ".join(spoken), expected)

    def test_single_oversized_word_keeps_every_phoneme(self):
        word = "a" * (2 * MAX_PHONEMES + 1)
        self.assertEqual(list(phoneme_chunks(word)), [
            "a" * MAX_PHONEMES, "a" * MAX_PHONEMES, "a",
        ])
