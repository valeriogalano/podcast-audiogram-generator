# Podcast Audiogram Generator

> **Vibe Coding experiment** — This project was built through Vibe Coding: iterative,
> AI-assisted development where the human steers intent and the AI writes most of the code.
> It works, it's tested, but it is first and foremost an experiment. Expect rough edges,
> quick evolution, and the occasional surprise. Issues and PRs are welcome.

Automatic audiogram generator for podcasts. Downloads episodes from an RSS feed, extracts
soundbites with their transcripts, and renders videos optimized for the major social platforms.

## At a glance

- Parse a podcast RSS feed to extract episodes, soundbites, transcripts, and cover art
- Download and save the full episode audio (MP3) and transcript (SRT) automatically
- Generate audiograms in 3 social-friendly formats: vertical (9:16), square (1:1), horizontal (16:9)
- Live transcript on video, animated waveform, and fully customizable colors/branding
- Optional Call-to-Action badge overlay (e.g. "Link in bio")
- Interactive CLI or fully automated via command-line flags or YAML config
- Manual soundbite support for feeds that do not include `<podcast:soundbite>` tags
- Customizable caption labels for easy localization
- Dry-run mode to preview timings and transcript text without generating any file

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
- Windows: download from https://ffmpeg.org/download.html and add `ffmpeg` to your PATH.

## Quick start

```bash
git clone https://github.com/vgalano/podcast-audiogram-generator.git
cd podcast-audiogram-generator

# 1) Create a virtual environment and install dependencies
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt

# 2) Copy and edit the example config
cp config.yaml.example config.yaml
$EDITOR config.yaml   # set feed_url and any other options

# 3) Run
.venv/bin/python -m audiogram_generator
```

## Running with the virtual environment

There are two equivalent ways to use the `.venv` after creating it.

**Option A — activate once per shell session (convenient for interactive use):**

```bash
source .venv/bin/activate           # macOS / Linux
.venv\Scripts\activate              # Windows

python -m audiogram_generator       # works for the rest of the session
python -m pytest tests/ -v
deactivate                          # when done
```

**Option B — invoke the venv Python directly (no activation needed, safer for scripts):**

```bash
.venv/bin/python -m audiogram_generator
.venv/bin/python -m pytest tests/ -v
```

Option B is the recommended approach in this README because it works regardless of which
shell or working directory you are in, and it makes the Python version explicit.

## Usage

### Interactive mode

Run without arguments to be guided through feed selection, episode selection, and soundbite
generation:

```bash
.venv/bin/python -m audiogram_generator
```

### Command-line mode

All parameters can be passed as flags for non-interactive or automated execution:

```bash
.venv/bin/python -m audiogram_generator [options]
```

Available options:

| Flag | Description |
|---|---|
| `--config PATH` | YAML configuration file |
| `--feed-url URL` | RSS feed URL (required if not in config) |
| `--episode N` | Episodes to process: `5`, `1,3,5`, `all`, or `last` |
| `--soundbites N` | Soundbites: `1`, `1,3`, or `all` |
| `--output-dir PATH` | Output directory (default: `./output`) |
| `--temp-dir PATH` | Temporary directory for intermediate files (default: `./temp`) |
| `--header-title-source` | Header title: `auto`, `podcast`, `episode`, `soundbite`, `none` |
| `--log-level LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `--dry-run` | Preview only — no files generated |
| `--full-episode` | Render the entire episode instead of individual soundbites |
| `--show-subtitles` / `--no-subtitles` | Force enable/disable on-video subtitles |
| `--use-episode-cover` / `--no-use-episode-cover` | Use episode-specific cover art when available |

Precedence: CLI flags > config file > built-in defaults.

Examples:

```bash
# Generate all soundbites for episode 142
.venv/bin/python -m audiogram_generator --episode 142 --soundbites all

# Generate soundbites 1 and 3 for episode 100
.venv/bin/python -m audiogram_generator --episode 100 --soundbites 1,3

# Custom feed and output directory
.venv/bin/python -m audiogram_generator \
  --feed-url https://example.com/feed.xml \
  --episode 5 --soundbites all --output-dir ~/videos

# Use a config file and override one option
.venv/bin/python -m audiogram_generator --config config.yaml --episode 150

# Most recent episode from the feed
.venv/bin/python -m audiogram_generator --episode last --soundbites all

# Episode-specific cover art
.venv/bin/python -m audiogram_generator --episode 142 --soundbites all --use-episode-cover
```

### Dry-run mode

Preview timings and transcript text without downloading or rendering anything. For each
selected soundbite it prints start, end, duration, and transcript text.

```bash
.venv/bin/python -m audiogram_generator --episode 142 --soundbites all --dry-run

# Without a config file
.venv/bin/python -m audiogram_generator --feed-url <RSS_URL> --episode 1 --soundbites 1,3 --dry-run
```

YAML equivalent:
```yaml
dry_run: true
```

### Full-episode audiogram

Render an audiogram for the entire episode instead of individual soundbites. Useful for
short episodes or complete promotional clips.

> **Note:** Full episodes can be 30–90 minutes long. Rendering time scales with duration —
> the tool warns you before starting.

```bash
.venv/bin/python -m audiogram_generator --episode 142 --full-episode
```

YAML equivalent:
```yaml
full_episode: true
```

### Subtitles and cover art

Control on-video subtitles and cover art via CLI flags or YAML. CLI flags always take
precedence.

```bash
# Disable on-video subtitles
.venv/bin/python -m audiogram_generator --no-subtitles

# Use episode-specific cover art (fallback to podcast cover if unavailable)
.venv/bin/python -m audiogram_generator --use-episode-cover
```

YAML:
```yaml
show_subtitles: false
use_episode_cover: true
```

When subtitles are disabled, video filenames include a `_nosubs` suffix
(e.g. `ep142_sb1_nosubs_vertical.mp4`) so they are easy to tell apart.

## Configuration

Settings are read from a YAML file. CLI flags override YAML values, which override
built-in defaults.

```bash
cp config.yaml.example config.yaml
```

Full annotated `config.yaml`:

```yaml
# REQUIRED
feed_url: https://example.com/podcast/feed.xml

# Output
output_dir: ./output
temp_dir: ./temp        # intermediate files, cleaned up automatically

# Selection
episode: last           # last, all, 142, or "1,3,5"
soundbites: "all"       # all, 1, or "1,3"

# Behavior
dry_run: false
full_episode: false
show_subtitles: true
use_episode_cover: false
header_title_source: auto   # auto | podcast | episode | soundbite | none

# SSL (default false to tolerate self-signed certs on some feeds)
verify_ssl: false

# Colors — RGB arrays [R, G, B] in 0–255
colors:
  primary: [242, 101, 34]       # header, footer, waveform bars
  background: [235, 213, 197]   # central area background
  text: [255, 255, 255]         # header text
  transcript_bg: [0, 0, 0]      # subtitle box background

# Fonts — path to a .ttf or .ttc file (optional)
fonts:
  header: "/path/to/font.ttf"
  transcript: "/path/to/font.ttf"

# Video formats
formats:
  vertical:
    width: 1080
    height: 1920
    enabled: true
    description: "Verticale 9:16 (Reels, Stories, Shorts, TikTok)"
  square:
    width: 1080
    height: 1080
    enabled: true
    description: "Quadrato 1:1 (Post Instagram, Twitter, Mastodon)"
  horizontal:
    width: 1920
    height: 1080
    enabled: false
    description: "Orizzontale 16:9 (YouTube)"

# Social hashtags (merged with feed keywords, duplicates removed)
hashtags:
  - podcast
  - tech

# Caption file labels — customize or translate these fixed strings
caption_labels:
  episode_prefix: "Episode"              # "Episode 42: Title"
  listen_full_prefix: "Listen to the full episode"   # "Listen to...: https://..."

# Call-to-Action badge — optional overlay text on the video
cta:
  enabled: false
  text: "Link in bio"
  # Vertical position per format (0.0 = top, 1.0 = bottom)
  vertical:
    y_offset: 0.82
  square:
    y_offset: 0.85
  horizontal:
    y_offset: 0.85

# Manual soundbites — for feeds without <podcast:soundbite> tags
manual_soundbites:
  "142":                      # episode number (string)
    - start: 120.5
      duration: 30.0
      text: "A very interesting moment"
  "unique-guid-here":         # or episode GUID
    - start: 500
      duration: 15
      text: "Another segment"
```

### Header title source

Configures what text appears in the video header bar:

| Value | Behaviour |
|---|---|
| `auto` | Episode title if available, otherwise podcast title (default) |
| `episode` | Always the episode title |
| `podcast` | Always the podcast title |
| `soundbite` | The soundbite title; falls back to episode/podcast if empty |
| `none` | No title in the header |

### Call-to-Action badge

When `cta.enabled: true`, a small pill-shaped badge is overlaid on the video at the
configured vertical position. Useful for "Link in bio" or similar social prompts.

```yaml
cta:
  enabled: true
  text: "Link in bio"
  vertical:
    y_offset: 0.82
```

### Manual soundbites

If your podcast feed does not include `<podcast:soundbite>` tags, define soundbites
manually in `config.yaml`. You can identify episodes by number or by their GUID:

```yaml
manual_soundbites:
  "142":
    - start: 120.5
      duration: 30.0
      text: "A very interesting moment"
  "unique-guid-here":
    - start: 500
      duration: 15
      text: "Another segment"
```

Manual soundbites are merged with any found in the feed, with manual ones appearing first.

### Workflow for precise soundbite timings

1. **Find the timestamps** — run the script once on the target episode. The full SRT
   transcript is saved to `output/ep{N}/ep{N}.srt`. Open it in a text editor to find
   exact timestamps (format: `HH:MM:SS,mmm`).
2. **Add to config** — set `start` (in seconds) and `duration` under `manual_soundbites`.
3. **Verify with dry-run** — check the extracted text without rendering:
   ```bash
   .venv/bin/python -m audiogram_generator --episode 142 --soundbites all --dry-run
   ```
4. **Generate** — once the preview looks right, remove `--dry-run` and run for real.

## Output structure

Files are organized in a two-level folder hierarchy inside `output_dir`:

```
output/
└── ep142/                          ← one folder per episode
    ├── ep142.mp3                   ← full episode audio
    ├── ep142.srt                   ← full episode transcript
    ├── ep142_full_vertical.mp4     ← full-episode mode only
    ├── ep142_full_square.mp4
    ├── sb1/                        ← one subfolder per soundbite
    │   ├── ep142_sb1.mp3
    │   ├── ep142_sb1.srt
    │   ├── ep142_sb1_caption.txt
    │   ├── ep142_sb1_vertical.mp4
    │   ├── ep142_sb1_square.mp4
    │   └── ep142_sb1_horizontal.mp4
    └── sb2/
        └── ...
```

When subtitles are disabled, video names include `_nosubs`:
`ep142_sb1_nosubs_vertical.mp4`.

Each `_caption.txt` file contains: episode number and title, soundbite title, full
transcript text, link to the full episode, and suggested hashtags.

## How an audiogram is composed

Each generated video frame consists of three vertical zones:

- **Header** — coloured bar at the top containing the episode/podcast/soundbite title
- **Central area** — podcast cover art with an animated waveform synchronized to the audio;
  the live transcript subtitle is overlaid here
- **Footer** — coloured bar at the bottom

Colors, fonts, and format dimensions are all configurable (see [Configuration](#configuration)).

## Tests

```bash
.venv/bin/python -m pytest tests/ -v --tb=short

# Single module
.venv/bin/python -m pytest tests/test_config.py -v

# Single test
.venv/bin/python -m pytest tests/test_config.py::TestConfig::test_configuration_precedence -v
```

## Dependencies

- feedparser >= 6.0.10
- moviepy >= 1.0.3
- pillow >= 10.0.0
- pydub >= 0.25.1
- numpy >= 1.24.0
- requests >= 2.31.0
- pyyaml >= 6.0
- audioop-lts >= 0.2.1 — required only on Python 3.13+ (replaces the removed stdlib `audioop`)

## Roadmap

- Better document subtitle configuration
- Handle hashtags with spaces
- Support for more than 3 formats
- Custom background images

## License

See the [LICENSE](LICENSE) file for details.
