# Podcast Audiogram Generator

> **Vibe Coding experiment** — This project was built through iterative, AI-assisted development where the human steers intent and the AI writes most of the code. It works, it's tested, but it is first and foremost an experiment. Expect rough edges, quick evolution, and the occasional surprise. Issues and PRs are welcome.

Automatic audiogram generator for podcasts. Downloads episodes from an RSS feed, extracts soundbites with their transcripts, and renders videos optimized for the major social platforms.

---

## How it works

The tool parses a podcast RSS feed, downloads the episode audio and transcript (SRT), then renders audiogram videos for the selected soundbites. Each video includes an animated waveform, a live transcript overlay, and a customizable header/footer. Output formats are vertical (9:16), square (1:1), and horizontal (16:9).

---

## Requirements

- Python >= 3.8
- FFmpeg

### Install FFmpeg

```bash
# macOS
brew install ffmpeg

# Linux (Ubuntu/Debian)
sudo apt-get install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html and add ffmpeg to your PATH
```

---

## Installation

```bash
git clone https://github.com/vgalano/podcast-audiogram-generator.git
cd podcast-audiogram-generator

python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt

cp config.yaml.example config.yaml
# Edit config.yaml and set feed_url and any other options
```

---

## Usage

All configuration lives in `config.yaml`. Once the file is set up, run:

```bash
.venv/bin/python -m audiogram_generator
```

CLI flags are available for lightweight overrides and debugging:

| Flag | Description |
|---|---|
| `--config PATH` | Path to a YAML configuration file (default: `./config.yaml`) |
| `--episode N` | Override the episode selection: `5`, `1,3,5`, `all`, or `last` |
| `--soundbites N` | Override the soundbite selection: `1`, `1,3`, or `all` |
| `--log-level LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `--dry-run` | Preview timings and subtitles — no files generated |
| `--force` | Overwrite existing output files instead of skipping them |
| `--limit N` | Process at most N soundbites per episode per run |

### Examples

```bash
# Use defaults from config.yaml
.venv/bin/python -m audiogram_generator

# Override episode and soundbites at the command line
.venv/bin/python -m audiogram_generator --episode 142 --soundbites all

# Most recent episode, dry run to preview timings
.venv/bin/python -m audiogram_generator --episode last --soundbites all --dry-run

# Re-generate only the first 3 soundbites of episode 142, overwriting existing files
.venv/bin/python -m audiogram_generator --episode 142 --soundbites all --limit 3 --force

# Use a different config file
.venv/bin/python -m audiogram_generator --config config.staging.yaml
```

---

## Configuration

```bash
cp config.yaml.example config.yaml
```

Key options in `config.yaml`:

```yaml
feed_url: https://example.com/podcast/feed.xml
output_dir: ./output
temp_dir: ./temp
episode: last           # last | all | 142 | "1,3,5"
soundbites: "all"       # all | 1 | "1,3"
dry_run: false
full_episode: false
show_subtitles: true
use_episode_cover: false
header_title_source: auto   # auto | podcast | episode | soundbite | none

colors:
  primary: [242, 101, 34]
  background: [235, 213, 197]
  text: [255, 255, 255]
  transcript_bg: [0, 0, 0]

formats:
  vertical:
    width: 1080
    height: 1920
    enabled: true
  square:
    width: 1080
    height: 1080
    enabled: true
  horizontal:
    width: 1920
    height: 1080
    enabled: false

hashtags:
  - podcast
  - tech

cta:
  enabled: false
  text: "Link in bio"

manual_soundbites:
  "142":
    - start: 120.5
      duration: 30.0
      text: "A very interesting moment"
```

See `config.yaml.example` for the full annotated reference.

---

## Output structure

```
output/
└── ep142/
    ├── ep142.mp3
    ├── ep142.srt
    ├── sb1/
    │   ├── ep142_sb1.mp3
    │   ├── ep142_sb1.srt
    │   ├── ep142_sb1_caption.txt
    │   ├── ep142_sb1_vertical.mp4
    │   └── ep142_sb1_square.mp4
    └── sb2/
        └── ...
```

When subtitles are disabled, video filenames include a `_nosubs` suffix.

---

## Tests

```bash
.venv/bin/python -m pytest tests/ -v --tb=short
```

---

## Dependencies

- feedparser >= 6.0.10
- moviepy >= 1.0.3
- pillow >= 10.0.0
- pydub >= 0.25.1
- numpy >= 1.24.0
- requests >= 2.31.0
- pyyaml >= 6.0
- audioop-lts >= 0.2.1 (Python 3.13+ only)

---

## Roadmap

- Better subtitle configuration documentation
- Handle hashtags with spaces
- Support for more than 3 output formats
- Custom background images

---

## Contributing

If you spot a bug or have a suggestion, feel free to open an **Issue** and then a **Pull Request**. All contributions are welcome!

---

## License

See the [LICENSE](LICENSE) file for details.