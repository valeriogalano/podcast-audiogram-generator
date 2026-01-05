# Podcast Audiogram Generator

Automatic audiogram generator for podcasts. It downloads episodes from an RSS feed, extracts soundbites with their transcripts, and generates audiogram videos optimized for major social platforms.

## At a glance

- Parse podcast RSS to extract episodes, soundbites, transcripts, and cover art
- Generate audiograms in 3 social-friendly formats: vertical (9:16), square (1:1), horizontal (16:9)
- Live transcript on video, animated waveform, and customizable colors/branding
- Interactive CLI or fully automatic via command-line flags or YAML config
- Dry‑run mode to preview timings and transcript text without generating files

## Requirements

- Python >= 3.8
- FFmpeg (for audio/video processing)

### Install FFmpeg

- macOS:
  ```bash
  brew install ffmpeg
  ```
- Linux (Ubuntu/Debian):
  ```bash
  sudo apt-get install ffmpeg
  ```
- Windows:
  Download from https://ffmpeg.org/download.html and add `ffmpeg` to your PATH.

## Quick start

```bash
git clone https://github.com/vgalano/podcast-audiogram-generator.git
cd podcast-audiogram-generator

# 1) Create and activate a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate            # on Windows: .venv\Scripts\activate

# 2) Upgrade pip and install dependencies
python -m pip install -U pip
pip install -r requirements.txt

# 3) Copy and edit the example config
cp config.yaml.example config.yaml
$EDITOR config.yaml                   # set your RSS feed URL and options

# 4) Run in interactive mode
python -m audiogram_generator
```

Tip: Keep using the same virtual environment in future sessions by running `source .venv/bin/activate` (or `.venv\Scripts\activate` on Windows) before commands.

## Usage

### Interactive mode

Run without arguments to be guided through podcast selection, episode selection, and soundbite generation:

```bash
python -m audiogram_generator
```

### Command-line mode

All parameters can be passed as flags for non‑interactive execution:

```bash
python -m audiogram_generator [options]
```

Available options:

- `--config PATH` — YAML configuration file
- `--feed-url URL` — RSS feed URL (required if not provided in config)
- `--episode EPISODES` — Episodes to process: `5`, `1,3,5`, `all`, or `last` (most recent)
- `--soundbites CHOICE` — Soundbites: `1`, `1,3`, or `all`
- `--output-dir PATH` — Output directory (default: `./output`)
- `--header-title-source CHOICE` — Source for the header title: `auto` (default), `podcast`, `episode`, `soundbite`, or `none`
- `--log-level LEVEL` — Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- `--dry-run` — Print timings and transcript text only (no files generated)
- `--show-subtitles` / `--no-subtitles` — Force enable/disable on‑video subtitles
- `--use-episode-cover` / `--no-use-episode-cover` — Prefer the episode-specific cover art when available (fallback to podcast cover)

Precedence: CLI flags > config file > defaults.

Examples:

```bash
# Generate all soundbites for episode 142
python -m audiogram_generator --episode 142 --soundbites all

# Generate soundbites 1 and 3 for episode 100
python -m audiogram_generator --episode 100 --soundbites 1,3

# Use a custom RSS feed and a custom output directory
python -m audiogram_generator --feed-url https://example.com/feed.xml \
  --episode 5 --soundbites all --output-dir ~/videos

# Use a configuration file and override an option
python -m audiogram_generator --config config.yaml --episode 150

# Process the most recent episode from the feed
python -m audiogram_generator --episode last --soundbites all

# Use the episode cover instead of the podcast cover (when available)
python -m audiogram_generator --episode 142 --soundbites all --use-episode-cover
```

### Dry‑run mode

Preview what will be generated without downloading or rendering audio/video. For each selected soundbite it prints start, end, duration, and transcript text (from SRT if available, otherwise the soundbite title).

From CLI:

```bash
python -m audiogram_generator --config config.yaml --episode 142 --soundbites all --dry-run

# Or without a config file
python -m audiogram_generator --feed-url <RSS_URL> --episode 1 --soundbites 1,3 --dry-run
```

Enable from config (optional):

```yaml
dry_run: true
```

### Subtitles and Cover options

Control on‑video subtitles and cover art preferences via CLI flags or YAML. CLI flags always win.

- Subtitles:
  - Disable: `python -m audiogram_generator --no-subtitles`
  - Enable:  `python -m audiogram_generator --show-subtitles` (default)
- Episode cover:
  - Enable:  `python -m audiogram_generator --use-episode-cover`
  - Disable: `python -m audiogram_generator --no-use-episode-cover` (default)

YAML (`config.yaml`):
```yaml
show_subtitles: false
use_episode_cover: true
```

When subtitles are disabled, generated video filenames include a `_nosubs` suffix to make files easy to identify, for example: `ep142_sb1_nosubs_vertical.mp4`.

## Configuration

The application reads settings from a YAML file (see `config.yaml.example`). CLI flags override YAML values, which in turn override internal defaults.

Start from the example and adjust to your needs:

```bash
cp config.yaml.example config.yaml
```

Example `config.yaml`:

```yaml
# REQUIRED
feed_url: https://pensieriincodice.it/podcast/index.xml

# Output
output_dir: ./output

# Selection
episode: 142
soundbites: "all"

# Behavior
dry_run: false
show_subtitles: true
use_episode_cover: false
header_title_source: auto

# Appearance (optional)
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
    enabled: true
  horizontal:
    enabled: false

# Social hashtags (merged with feed keywords, duplicates removed)
hashtags:
  - podcast
  - tech
  - development
```

Notes:
- RGB colors are expressed as `[R, G, B]` with values 0–255.
- Formats can be enabled/disabled and resized per needs.

### Header title source

Customize what title appears in the video header. Available values:
- `auto` (default): uses episode title if available, otherwise podcast title
- `podcast`: always use podcast title
- `episode`: always use episode title
- `soundbite`: use soundbite title
- `none`: hide the header title

CLI: `--header-title-source CHOICE`
YAML: `header_title_source: CHOICE`

### Caption labels (customizable fixed strings)

You can customize the fixed strings used in the generated caption `.txt` files, for example to localize them. Add the following section to your `config.yaml`:

```
caption_labels:
  # Prefix before the episode number and title
  # Result example: "Episode 42: Title"
  episode_prefix: "Episode"
  # Text before the link to the full episode
  # Result example: "Listen to the full episode: https://..."
  listen_full_prefix: "Listen to the full episode"
```

If omitted, the defaults are used (`Episode` and `Listen to the full episode`).

## Output

Files are saved to `output/` by default.

Videos:
```
ep{episode_number}_sb{soundbite_number}_{format}.mp4
# When subtitles are disabled:
ep{episode_number}_sb{soundbite_number}_nosubs_{format}.mp4
```

Caption file:
```
ep{episode_number}_sb{soundbite_number}_caption.txt
```

Example for soundbite 1 of episode 142:
- `ep142_sb1_vertical.mp4`
- `ep142_sb1_square.mp4`
- `ep142_sb1_horizontal.mp4`
- `ep142_sb1_caption.txt`

If subtitles are disabled:
- `ep142_sb1_nosubs_vertical.mp4`
- `ep142_sb1_nosubs_square.mp4`
- `ep142_sb1_nosubs_horizontal.mp4`

Each `_caption.txt` contains: episode title/number, soundbite title, full transcript text, link to full episode, and suggested hashtags.

## Project structure

```
podcast-audiogram-generator/
├── audiogram_generator/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── config.py
│   ├── audio_utils.py
│   └── video_generator.py
├── tests/
├── output/
├── requirements.txt
└── setup.py
```

## How an audiogram is composed

Each generated video includes:
- Header with a "LISTEN" label and audio icons
- Central area: podcast cover and animated waveform synchronized with audio
- Live transcript at the bottom of the central area
- Footer with podcast title and episode/soundbite title

## Tests

Run the test suite with Python’s unittest:

```bash
python -m unittest discover tests
```

Examples:

```bash
# Specific module
python -m unittest tests.test_config -v

# Single test
python -m unittest tests.test_config.TestConfig.test_configuration_precedence -v
```

## Dependencies

- feedparser (≥6.0.10)
- moviepy (≥1.0.3)
- pillow (≥10.0.0)
- pydub (≥0.25.1)
- audioop-lts (≥0.2.1) — only required on Python 3.13+ where stdlib `audioop` was removed
- numpy (≥1.24.0)
- requests (≥2.31.0)
- pyyaml (≥6.0)

Note for Python 3.13+: The standard library module `audioop` was removed. We use the maintained backport `audioop-lts` to restore compatibility for audio processing libraries like `pydub`. It is declared as a conditional dependency in `requirements.txt` and will be installed automatically on Python 3.13+.

## Roadmap

- Better document subtitle configuration
- Handle tags with spaces

## License

See the [LICENSE](LICENSE) file for details.

## Note

This project started as a *vibe code* experiment and may evolve quickly. Issues and PRs are welcome.
