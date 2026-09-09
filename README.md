# Video Player — Frame Extractor

Desktop tools for playing a video, extracting PNG frames / PDF, clipping MP4 segments, and (optionally) batch-cropping images to Excel.

The main app is **`get_png_video 12a.py`**: a dark-themed Tkinter player with a large video window and three tabs.

## Requirements

- **Windows** (tested with Python 3 + Tkinter)
- **[VLC media player](https://www.videolan.org/vlc/)** — required by `python-vlc`
- **[FFmpeg](https://ffmpeg.org/)** on `PATH` — required for video clips and for PNG extract when OpenCV cannot write the file (including Unicode paths)
- Python packages:

```text
opencv-python>=4.5.0
Pillow>=9.0.0
python-vlc>=3.0.0
```

For the image cropper’s Excel export, also install `openpyxl`.

```bash
pip install opencv-python Pillow python-vlc openpyxl
```

## Run

From this folder:

```bash
python "get_png_video 12a.py"
```

Image cropper:

```bash
python crop_images.py
```

On this machine you can also use `run_get_png_pdf_mp4_video_12a.bat` / `run_crop_images.bat` (they activate a local conda env).

## Time format

Editable time fields use **`MM:SS:mmm`** (minutes : seconds : milliseconds), for example `00:23:151` or `08:47:522`.

The seek bar labels use `HH:MM:SS`. **Step Time** is in seconds (for example `10.0` or `2.35`).

## Layout

Shared on every tab: video display, seek bar, **Open Video**, **Step Time**, Backward / Play / Pause / Stop / Forward, **Go to time**, **AB Play Time**.

| Tab | Controls |
| --- | --- |
| **Home** | Start Time, End Time, Get Video Time, playback speed (Set + presets + editable speed) |
| **Extract Video** | Start Time, End Time (same values as Home), Rotate Video, Extract Video, Dumb Video, Clear All MP4s |
| **Extract PNG** | Auto extract start / Copy Go, Auto extract stop / Copy Time, Every, Get Video Time, Extract Frame (PNG), Auto Extract Frame (PNG), Create PDF, Clear All PNGs |

Start Time / End Time stay in sync between Home and Extract Video.

## What each action does

### Playback (all tabs)

- **Open Video** — pick a file (`mp4`, `mkv`, `avi`, `mov`, and other common formats). Playback does **not** start until you click Play.
- **Go** — jump to the time in **Go to time**.
- **Forward / Backward** — step by **Step Time** seconds.
- **AB Play Time** — loop between **Start Time** and **End Time**. Click **Play** to leave loop mode and play normally.
- **Start Time / End Time** buttons — copy the current **Go to time** into that field.

### Home

- **Set** / speed buttons / **Playback Speed** — change VLC rate. Opening a video sets the default speed to **1.0x**.
- **Get Video Time** — append the current **Go to time** (as seconds) to `VideoTime/VideoTime.txt`. Opening a new video deletes that file.

### Extract Video

- **Extract Video** — cut **Start Time** → **End Time**. Output **duration stays End − Start**. Always writes an `_av.mp4` (video + audio). Check **Dumb Video** to also write a silent `_dumb.mp4`.
- **No Rotation + 1.0x** — fast **stream copy** (`ffmpeg -c copy`, same approach as H_SplitMP4-GUI `Process`). Much faster than re-encoding.
- **Rotate Video** or playback speed ≠ 1.0x — existing **re-encode** path (libx264 / filters). Rotation options: `No Rotation`, 90/180 left or right. Non-1.0x speed changes frame density only (for example `0.5x` packs twice as many frames into the same length).
- **Clear All MP4s** — deletes files in the `mp4` folder.

### Extract PNG

- **Copy Go** — copy **Go to time** into **Auto extract start**.
- **Copy Time** — copy **Start Time** / **End Time** into **Auto extract start** / **Auto extract stop**.
- **Auto extract start / stop** — absolute clock times (stop is not a duration). **Every** is the interval between frames.
- **Extract Frame (PNG)** — one frame at the current playhead.
- **Auto Extract Frame (PNG)** — frames from start to stop, every interval.
- **Create PDF** — all PNGs in `png/`, sorted by name, saved as `videoPDF.pdf`.
- **Clear All PNGs** — delete PNGs and `TIME.txt`; next file is `00001.png`.
- **Get Video Time** — same as on Home.

## Output folders

Created next to the opened video:

```text
<video folder>/
  png/                 00001.png, 00002.png, …  TIME.txt  videoPDF.pdf
  mp4/                 <name>_<start>_<end>_speed<n>x_av.mp4
                       …_dumb.mp4   (only if Dumb Video is checked)
  VideoTime/           VideoTime.txt   (seconds, one per line)
```

`TIME.txt` lines look like:

```text
00001.png, 00:00:16
00002.png, 00:01:05
```

PNG names are `00001.png`, `00002.png`, … continuing from the highest existing number in `png/`.

## Tests

```bash
python -m unittest test_extract_video.py -v
```

Covers time conversion, auto-extract start/stop/Every math, tab layout, ffmpeg command shape, and (if `ffmpeg`/`ffprobe` are on `PATH`) a short extract-duration check.

## Image cropper (`crop_images.py`)

1. **Browse Folder** and preview images.
2. Drag a rectangle on the preview, then crop every image into a `cropImages` subfolder.
3. Export to **`cropImages.xlsx`** (sort by name or modify time; set rows, columns, and gaps). Excel export needs `openpyxl`.
