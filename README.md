# YouTube Audio Downloader

YouTube 영상에서 오디오만 추출해 파일로 저장하는 간단한 CLI 도구입니다.

## 요구 사항

- Python 3.8+
- [ffmpeg](https://ffmpeg.org/) (mp3 등으로 변환할 때 필요)

## 설치

```bash
pip install -r requirements.txt
```

ffmpeg 설치 (예시):

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt-get install -y ffmpeg
```

## 사용법

```bash
# 기본: ./downloads 폴더에 mp3 (192kbps)로 저장
python download_audio.py "https://youtu.be/gSWxf6ar6pM"

# 출력 폴더, 포맷, 비트레이트 지정
python download_audio.py "https://youtu.be/gSWxf6ar6pM" \
  --output-dir ./music \
  --format m4a \
  --quality 256

# 처음 15초만 잘라서 저장
python download_audio.py "https://youtu.be/gSWxf6ar6pM" --duration 15

# 30초 지점부터 15초 구간만 저장
python download_audio.py "https://youtu.be/gSWxf6ar6pM" --start 30 --duration 15
```

### 옵션

| 옵션 | 설명 | 기본값 |
| --- | --- | --- |
| `url` | 다운로드할 YouTube 영상 URL (필수) | - |
| `-o`, `--output-dir` | 저장 폴더 | `downloads` |
| `-f`, `--format` | 오디오 포맷 (`mp3`, `m4a`, `wav`, `opus`, `aac`, `flac`) | `mp3` |
| `-q`, `--quality` | 비트레이트 (kbps) | `192` |
| `-s`, `--start` | 잘라낼 시작 지점 (초) | `0` |
| `-d`, `--duration` | 잘라낼 길이 (초). 미지정 시 전체 다운로드 | 없음 |

## 주의 사항

저작권이 보호되는 콘텐츠를 다운로드할 때는 해당 콘텐츠의 라이선스와 YouTube 이용약관을 반드시 준수하세요.
