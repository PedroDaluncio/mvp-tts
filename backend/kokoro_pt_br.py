"""Generate a Brazilian Portuguese WAV file with Kokoro."""

import argparse
from collections.abc import Callable, Iterator
from functools import cache
from io import BytesIO
from pathlib import Path
from typing import Literal, get_args

import soundfile as sf
from kokoro import KPipeline
from starlette.config import Config


Voice = Literal["pf_dora", "pm_alex", "pm_santa"]
MAX_PHONEMES = 510  # Kokoro's per-inference phoneme string limit.
env_file = Path(__file__).with_name(".env")
config = Config(env_file if env_file.is_file() else None)


def create_pipeline() -> KPipeline:
    return KPipeline(
        lang_code="p",
        repo_id=config("KOKORO_REPO_ID", default="hexgrad/Kokoro-82M"),
        device=config("KOKORO_DEVICE", default="") or None,
    )


get_pipeline = cache(create_pipeline)


def phoneme_chunks(phonemes: str) -> Iterator[str]:
    start = 0
    while start < len(phonemes):
        end = min(start + MAX_PHONEMES, len(phonemes))
        if end < len(phonemes):
            # Prefer a sentence ending, then a word boundary. A single oversized
            # word can span calls so its remaining phonemes are still spoken.
            punctuation = max(phonemes.rfind(mark, start, end) for mark in ".!?")
            if punctuation >= start:
                end = punctuation + 1
            else:
                space = phonemes.rfind(" ", start + 1, end + 1)
                if space != -1:
                    end = space
        chunk = phonemes[start:end].strip()
        if chunk:
            yield chunk
        start = end


def synthesize(
    text: str,
    voice: Voice,
    *,
    checkpoint: Callable[[], None] = lambda: None,
    pipeline: KPipeline | None = None,
) -> bytes:
    """Return mono, 24 kHz PCM audio in a WAV container."""
    if not text.strip():
        raise ValueError("Please provide some text to read aloud.")

    if pipeline is None:
        pipeline = get_pipeline()
    wav = BytesIO()
    with sf.SoundFile(wav, mode="w", samplerate=24000, channels=1, format="WAV", subtype="PCM_16") as writer:
        for paragraph in text.splitlines():
            if not paragraph.strip():
                continue
            checkpoint()
            phonemes, _ = pipeline.g2p(paragraph.strip())
            for chunk in phoneme_chunks(phonemes):
                checkpoint()
                for result in pipeline.generate_from_tokens(chunk, voice=voice):
                    writer.write(result.audio.cpu().numpy())
        checkpoint()
        if writer.frames == 0:
            raise ValueError("Kokoro produced no speech for this text.")
    return wav.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "text", nargs="?",
        default="Bom dia! O café está pronto. Vamos tomar uma xícara antes de sair?",
        help="Brazilian Portuguese text to read aloud",
    )
    parser.add_argument("--voice", choices=get_args(Voice), default="pf_dora")
    parser.add_argument("--output", type=Path, default=Path("exemplo_pt_br.wav"))
    args = parser.parse_args()
    try:
        audio = synthesize(args.text, args.voice)
    except ValueError as exc:
        parser.error(str(exc))
    args.output.write_bytes(audio)
    print(f"Saved {args.output} ({args.voice})")


if __name__ == "__main__":
    main()
