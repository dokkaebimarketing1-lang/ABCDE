#!/usr/bin/env python3
"""Download audio from a YouTube URL as an MP3 file, optionally trimmed.

Tries yt-dlp first, then falls back to pytubefix if yt-dlp can't download
(e.g. when YouTube blocks yt-dlp from cloud-IP runners).
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def _format_ts(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def _ensure_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required but not found on PATH")


def _ffmpeg_convert(
    src: Path,
    dst: Path,
    audio_format: str,
    quality: str,
    start: float,
    duration: float | None,
) -> None:
    _ensure_ffmpeg()
    cmd = ["ffmpeg", "-y", "-i", str(src)]
    if start:
        cmd += ["-ss", _format_ts(start)]
    if duration is not None:
        cmd += ["-t", _format_ts(duration)]
    cmd += ["-vn"]
    if audio_format == "mp3":
        cmd += ["-codec:a", "libmp3lame", "-b:a", f"{quality}k"]
    elif audio_format == "m4a":
        cmd += ["-codec:a", "aac", "-b:a", f"{quality}k"]
    elif audio_format == "wav":
        cmd += ["-codec:a", "pcm_s16le"]
    elif audio_format == "opus":
        cmd += ["-codec:a", "libopus", "-b:a", f"{quality}k"]
    elif audio_format == "aac":
        cmd += ["-codec:a", "aac", "-b:a", f"{quality}k"]
    elif audio_format == "flac":
        cmd += ["-codec:a", "flac"]
    cmd.append(str(dst))
    subprocess.run(cmd, check=True)


def _download_with_ytdlp(
    url: str,
    output_dir: Path,
    audio_format: str,
    quality: str,
    start: float,
    duration: float | None,
) -> Path:
    import yt_dlp

    suffix = f"_{int(duration)}s" if duration else ""
    outtmpl = str(output_dir / f"%(title)s{suffix}.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": False,
        "force_ipv4": True,
        "retries": 10,
        "fragment_retries": 10,
        "extractor_retries": 10,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "tv", "web"],
                "player_skip": ["webpage", "configs"],
            }
        },
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Mobile Safari/537.36"
            ),
        },
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": audio_format,
                "preferredquality": quality,
            }
        ],
    }
    if duration is not None:
        ydl_opts["postprocessor_args"] = {
            "ffmpegextractaudio": ["-ss", _format_ts(start), "-t", _format_ts(duration)],
        }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return Path(ydl.prepare_filename(info)).with_suffix(f".{audio_format}")


def _sanitize(name: str) -> str:
    keep = "-_.() "
    return "".join(c for c in name if c.isalnum() or c in keep).strip() or "audio"


def _download_with_pytubefix(
    url: str,
    output_dir: Path,
    audio_format: str,
    quality: str,
    start: float,
    duration: float | None,
) -> Path:
    from pytubefix import YouTube

    yt = YouTube(url, "WEB")
    stream = yt.streams.get_audio_only()
    if stream is None:
        # Fall back to highest-bitrate audio of any type.
        stream = yt.streams.filter(only_audio=True).order_by("abr").desc().first()
    if stream is None:
        raise RuntimeError("pytubefix could not find any audio stream")

    title = _sanitize(yt.title or "audio")
    suffix = f"_{int(duration)}s" if duration else ""
    raw_path = output_dir / f"{title}.{stream.subtype or 'm4a'}"
    stream.download(output_path=str(output_dir), filename=raw_path.name)

    final_path = output_dir / f"{title}{suffix}.{audio_format}"
    _ffmpeg_convert(raw_path, final_path, audio_format, quality, start, duration)
    if raw_path.exists() and raw_path != final_path:
        raw_path.unlink()
    return final_path


def download_audio(
    url: str,
    output_dir: Path,
    audio_format: str = "mp3",
    quality: str = "192",
    start: float = 0.0,
    duration: float | None = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    try:
        return _download_with_ytdlp(url, output_dir, audio_format, quality, start, duration)
    except Exception as e:
        errors.append(f"yt-dlp: {e}")
        sys.stderr.write(f"\nyt-dlp failed: {e}\nFalling back to pytubefix...\n")

    try:
        return _download_with_pytubefix(url, output_dir, audio_format, quality, start, duration)
    except Exception as e:
        errors.append(f"pytubefix: {e}")

    raise RuntimeError("All downloaders failed:\n  " + "\n  ".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="Download audio from a YouTube URL.")
    parser.add_argument("url", help="YouTube video URL (e.g. https://youtu.be/...)")
    parser.add_argument(
        "-o", "--output-dir", default="downloads",
        help="Directory to save the audio file (default: ./downloads)",
    )
    parser.add_argument(
        "-f", "--format", default="mp3",
        choices=["mp3", "m4a", "wav", "opus", "aac", "flac"],
        help="Audio format (default: mp3). Non-mp3 formats require ffmpeg.",
    )
    parser.add_argument(
        "-q", "--quality", default="192",
        help="Audio bitrate in kbps (default: 192)",
    )
    parser.add_argument(
        "-s", "--start", type=float, default=0.0,
        help="Start offset in seconds when trimming (default: 0)",
    )
    parser.add_argument(
        "-d", "--duration", type=float, default=None,
        help="Duration in seconds to keep. Omit to download the full track.",
    )
    args = parser.parse_args()

    try:
        path = download_audio(
            args.url, Path(args.output_dir), args.format, args.quality,
            args.start, args.duration,
        )
    except Exception as e:
        sys.stderr.write(f"Download failed: {e}\n")
        return 1

    print(f"\nSaved: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
