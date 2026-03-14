# CLAUDE.md

## Project overview

Automated audiogram video generator for podcasts. Downloads audio and transcripts from RSS
feeds, extracts soundbites, and renders videos in vertical (9:16), square (1:1), and horizontal
(16:9) formats for social media distribution.

**Entry point:** `audiogram_generator/cli.py` → `main()`
**Rendering engine:** `audiogram_generator/video_generator.py` + `rendering/facade.py` (stable API)
**Configuration:** `config.yaml` (YAML) deep-merged in `audiogram_generator/config.py`

---

## Running tests

### Known venv issue

The venv lives at `venv/` but was created under a different project path (`PycharmProjects/`
instead of `PyCharmMiscProject/`). The shebang in `venv/bin/pytest` points to the old,
non-existent path, so direct invocation fails:

```bash
# BROKEN — shebang points to old path
venv/bin/pytest tests/

# BROKEN — pytest not installed in system python
python3 -m pytest tests/
```

### Correct command

Use `.venv` (not `venv` — that one has broken symlinks). Always invoke pytest via the venv
Python interpreter using `-m pytest`:

```bash
.venv/bin/python -m pytest tests/ -v --tb=short 2>&1
```

Since shell state does not persist between Bash tool calls, run everything in a single command:

```bash
# Run the full test suite
.venv/bin/python -m pytest tests/ -v --tb=short 2>&1

# Run a single test file
.venv/bin/python -m pytest tests/test_config.py -v 2>&1

# Run a single test case
.venv/bin/python -m pytest tests/test_config.py::TestConfig::test_defaults -v 2>&1
```

> Always append `2>&1` to capture stderr, where pytest writes warnings and import errors.

---

## Project structure

```
audiogram_generator/
├── cli.py                  # Orchestration and CLI (main entry point)
├── config.py               # YAML configuration with deep merge
├── audio_utils.py          # Audio download and segment extraction
├── video_generator.py      # Frame rendering engine (PIL + MoviePy)
├── core/
│   ├── timeutils.py        # SRT timestamp parse/format
│   ├── selections.py       # Episode/soundbite selection parsing
│   └── captioning.py       # Caption and SRT generation
├── rendering/
│   └── facade.py           # Stable API wrapper around video_generator
└── services/
    ├── rss.py              # RSS feed fetch and parse
    ├── transcript.py       # SRT fetch and parse
    ├── assets.py           # Image download
    └── errors.py           # Custom exceptions
tests/                      # pytest suite (unittest.TestCase style)
```

---

## Testing conventions

- All network I/O (`fetch_srt`, `download_audio`, `download_image`, RSS fetching) must be mocked.
- `audio_utils` uses lazy imports (`from pydub import AudioSegment` inside functions); patch
  `pydub.AudioSegment.from_file` directly, not `audiogram_generator.audio_utils.AudioSegment`.
- Video rendering (`generate_audiogram`) must always be mocked — it requires FFmpeg and is slow.
- For `video_generator` unit tests, mock `ImageFont.truetype` and `Image.open` to avoid
  requiring real fonts or image files on disk.
- Smoke render tests should use a minimal size (e.g. 64×64) with a synthetic `Image.new` logo.
- The improvement roadmap and task tracking live in `IMPROVEMENT_PLAN.md`.
