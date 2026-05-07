#!/usr/bin/env python3
"""Download audio from a YouTube URL as an MP3 file."""

import argparse
import sys
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    sys.stderr.write(
        "yt-dlp is not installed. Install dependencies with:\n"
        "  pip install -r requirements.txt\n"
    )
    sys.exit(1)


def download_audio(url: str, output_dir: Path, audio_format: str = "mp3", quality: str = "192") -> Path:
    """Download the audio track of a YouTube video.

    Returns the path to the resulting audio file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    outtmpl = str(output_dir / "%(title)s.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": False,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": audio_format,
                "preferredquality": quality,
            }
        ],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        # After post-processing the file extension becomes audio_format.
        final_path = Path(ydl.prepare_filename(info)).with_suffix(f".{audio_format}")

    return final_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Download audio from a YouTube URL.")
    parser.add_argument("url", help="YouTube video URL (e.g. https://youtu.be/...)")
    parser.add_argument(
        "-o",
        "--output-dir",
        default="downloads",
        help="Directory to save the audio file (default: ./downloads)",
    )
    parser.add_argument(
        "-f",
        "--format",
        default="mp3",
        choices=["mp3", "m4a", "wav", "opus", "aac", "flac"],
        help="Audio format (default: mp3). Non-mp3 formats require ffmpeg.",
    )
    parser.add_argument(
        "-q",
        "--quality",
        default="192",
        help="Audio bitrate in kbps (default: 192)",
    )
    args = parser.parse_args()

    try:
        path = download_audio(args.url, Path(args.output_dir), args.format, args.quality)
    except yt_dlp.utils.DownloadError as e:
        sys.stderr.write(f"Download failed: {e}\n")
        return 1

    print(f"\nSaved: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
