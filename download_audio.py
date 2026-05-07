#!/usr/bin/env python3
"""Download audio from a YouTube URL as an MP3 file, optionally trimmed."""

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


def _format_ts(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def download_audio(
    url: str,
    output_dir: Path,
    audio_format: str = "mp3",
    quality: str = "192",
    start: float = 0.0,
    duration: float | None = None,
) -> Path:
    """Download the audio track of a YouTube video.

    If ``duration`` is set, only that many seconds (starting at ``start``) are kept.
    Returns the path to the resulting audio file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    suffix = f"_{int(duration)}s" if duration else ""
    outtmpl = str(output_dir / f"%(title)s{suffix}.%(ext)s")

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

    if duration is not None:
        # Pass -ss/-t to ffmpeg used by the extract-audio post-processor.
        ydl_opts["postprocessor_args"] = {
            "ffmpegextractaudio": ["-ss", _format_ts(start), "-t", _format_ts(duration)],
        }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
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
    parser.add_argument(
        "-s",
        "--start",
        type=float,
        default=0.0,
        help="Start offset in seconds when trimming (default: 0)",
    )
    parser.add_argument(
        "-d",
        "--duration",
        type=float,
        default=None,
        help="Duration in seconds to keep. Omit to download the full track.",
    )
    args = parser.parse_args()

    try:
        path = download_audio(
            args.url,
            Path(args.output_dir),
            args.format,
            args.quality,
            args.start,
            args.duration,
        )
    except yt_dlp.utils.DownloadError as e:
        sys.stderr.write(f"Download failed: {e}\n")
        return 1

    print(f"\nSaved: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
