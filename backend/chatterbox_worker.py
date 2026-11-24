# /// script
# requires-python = ">=3.10,<3.11"
# dependencies = [
#   "torch==2.8.0", "torchaudio==2.8.0", "numpy==1.26.0",
#   "resampy==0.4.3", "librosa==0.10.0", "s3tokenizer", "transformers==4.46.3",
#   "diffusers==0.29.0", "omegaconf==2.3.0", "resemble-perth==1.0.1",
#   "silero-vad==5.1.2", "conformer==0.3.2", "safetensors", "soundfile",
#   "huggingface-hub==0.25.2", "setuptools<81",
# ]
# [[tool.uv.index]]
# name = "cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# [tool.uv.sources]
# torch = { index = "cpu" }
# torchaudio = { index = "cpu" }
# ///
import json
import os
import sys
from io import BytesIO
from textwrap import wrap
from pathlib import Path
from tempfile import TemporaryDirectory

import soundfile as sf
import torch
from huggingface_hub import hf_hub_download, snapshot_download


def load_model():
    code = snapshot_download(
        "ResembleAI/Chatterbox-Multilingual-TTS-pt-br", repo_type="space",
        revision="9e515821e826e207cd617a0fdd0223899ed108ea",
        allow_patterns=["chatterbox/src/**/*.py"],
    )
    sys.path.insert(0, str(Path(code) / "chatterbox/src"))
    from chatterbox.tts import ChatterboxTTS

    torch.set_num_threads(int(os.getenv("OMP_NUM_THREADS", "4")))
    assets = {
        "ResembleAI/Chatterbox-Multilingual-pt-br": [
            "t3_pt_br.safetensors", "s3gen_v3.pt", "grapheme_mtl_merged_expanded_v1.json",
        ],
        "ResembleAI/chatterbox": ["ve.pt", "conds.pt"],
    }
    with TemporaryDirectory() as directory:
        for repo, files in assets.items():
            for name in files:
                (Path(directory) / name).symlink_to(hf_hub_download(repo, name))
        return ChatterboxTTS.from_local(directory, device="cpu")

def synthesize(model, text):
    output = BytesIO()
    with torch.inference_mode(), sf.SoundFile(
        output, mode="w", samplerate=model.sr, channels=1, format="WAV", subtype="PCM_16",
    ) as wav:
        for line in text.splitlines():
            for chunk in wrap(line, width=240):
                audio = model.generate(chunk, language_id="pt").squeeze(0).cpu()
                if not audio.numel() or not audio.isfinite().all():
                    raise RuntimeError("Invalid Chatterbox audio")
                wav.write(audio.numpy())
    return output.getvalue()


if __name__ == "__main__":
    # Reserve the original stdout for length-prefixed WAVs. Model logs go to stderr.
    with os.fdopen(os.dup(sys.stdout.fileno()), "wb") as replies:
        os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
        model = load_model()
        for request in sys.stdin:
            payload = json.loads(request)
            default_conditionals = model.conds
            try:
                if payload["reference"]:
                    model.prepare_conditionals(payload["reference"])
                audio = synthesize(model, payload["text"])
            finally:
                model.conds = default_conditionals
            replies.write(len(audio).to_bytes(8, "big"))
            replies.write(audio)
            replies.flush()
