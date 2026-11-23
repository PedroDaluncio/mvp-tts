"""Generate a Brazilian Portuguese WAV with Microsoft's Edge TTS service and FFmpeg."""

import argparse
import asyncio
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal, get_args

import edge_tts
from anyio import run_process


Voice = Literal["pt-BR-FranciscaNeural", "pt-BR-AntonioNeural"]


async def _decode_wav(mp3: Path, wav: Path) -> None:
    try:
        await run_process(
            ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-xerror",
             "-f", "mp3", "-i", str(mp3), "-ac", "1", "-ar", "24000",
             "-c:a", "pcm_s16le", str(wav)],
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Install FFmpeg to convert Edge TTS audio to WAV.") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode(errors="replace").strip()
        raise RuntimeError(f"FFmpeg could not decode the Edge TTS audio: {detail}") from exc


async def synthesize(text: str, voice: Voice) -> bytes:
    """Send text to Edge TTS and return mono, 24 kHz PCM-16 WAV bytes."""
    text = text.strip()
    if not text:
        raise ValueError("Please provide some text to read aloud.")
    if voice not in get_args(Voice):
        raise ValueError(f"Unsupported Brazilian Portuguese Edge voice: {voice}")

    with TemporaryDirectory() as directory:
        mp3 = Path(directory) / "speech.mp3"
        wav = Path(directory) / "speech.wav"
        await edge_tts.Communicate(text, voice).save(str(mp3))
        if not mp3.stat().st_size:
            raise RuntimeError("Edge TTS returned no audio.")
        await _decode_wav(mp3, wav)
        return wav.read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text", help="Brazilian Portuguese text to read aloud")
    parser.add_argument("--voice", choices=get_args(Voice), default="pt-BR-FranciscaNeural")
    parser.add_argument("--output", type=Path, default=Path("exemplo_edge_pt_br.wav"))
    args = parser.parse_args()
    audio = asyncio.run(synthesize(args.text, args.voice))
    args.output.write_bytes(audio)
    print(f"Saved {args.output} ({args.voice})")


if __name__ == "__main__":
    main()
