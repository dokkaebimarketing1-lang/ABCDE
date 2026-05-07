#!/usr/bin/env python3
"""Download audio from a YouTube URL as an MP3 file, optionally trimmed.

Tries yt-dlp first, then falls back to pytubefix if yt-dlp can't download
(e.g. when YouTube blocks yt-dlp from cloud-IP runners).
"""

import argparse
import json
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
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


PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://api-piped.mha.fi",
    "https://pipedapi.tokhmi.xyz",
    "https://pipedapi.adminforge.de",
    "https://pipedapi.smnz.de",
]


def _extract_video_id(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.hostname in ("youtu.be",):
        return parsed.path.lstrip("/")
    qs = urllib.parse.parse_qs(parsed.query)
    if "v" in qs:
        return qs["v"][0]
    parts = [p for p in parsed.path.split("/") if p]
    if parts and parts[0] in ("shorts", "live", "embed") and len(parts) > 1:
        return parts[1]
    raise ValueError(f"Cannot extract video id from URL: {url}")


def _http_json(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "audio-clip/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_download(url: str, dst: Path, timeout: int = 120) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "audio-clip/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(dst, "wb") as f:
        shutil.copyfileobj(resp, f, length=65536)


def _download_with_piped(
    url: str,
    output_dir: Path,
    audio_format: str,
    quality: str,
    start: float,
    duration: float | None,
) -> Path:
    video_id = _extract_video_id(url)
    last_err: Exception | None = None
    for inst in PIPED_INSTANCES:
        try:
            data = _http_json(f"{inst}/streams/{video_id}")
            streams = data.get("audioStreams") or []
            if not streams:
                raise RuntimeError(f"no audioStreams from {inst}")
            best = max(streams, key=lambda s: s.get("bitrate", 0))
            title = _sanitize(data.get("title") or video_id)
            ext = best.get("format", "mp4").lower()
            if ext == "m4a":
                ext = "m4a"
            elif "opus" in ext or "webm" in ext:
                ext = "webm"
            else:
                ext = "m4a"
            raw = output_dir / f"{title}.{ext}"
            _http_download(best["url"], raw)
            suffix = f"_{int(duration)}s" if duration else ""
            final = output_dir / f"{title}{suffix}.{audio_format}"
            _ffmpeg_convert(raw, final, audio_format, quality, start, duration)
            if raw.exists() and raw != final:
                raw.unlink()
            return final
        except Exception as e:
            last_err = e
            sys.stderr.write(f"piped {inst} failed: {e}\n")
            continue
    raise RuntimeError(f"All Piped instances failed: {last_err}")


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
    for name, fn in (
        ("yt-dlp", _download_with_ytdlp),
        ("pytubefix", _download_with_pytubefix),
        ("piped", _download_with_piped),
    ):
        try:
            return fn(url, output_dir, audio_format, quality, start, duration)
        except Exception as e:
            sys.stderr.write(f"\n{name} failed: {e}\nTrying next backend...\n")
            errors.append(f"{name}: {e}")

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
