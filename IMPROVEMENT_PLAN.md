# Piano di Migliorie — Audiogram Generator

## Performance

| # | Fix | File | Impatto | Stato |
|---|-----|------|---------|-------|
| P1 | Logo pre-caricato una volta sola (no `Image.open` + LANCZOS per frame) | `video_generator.py` | Alto | ✅ Done |
| P2 | Sensitivities waveform pre-computate (rimosso `np.random.seed` dal loop frame) | `video_generator.py` | Basso | ✅ Done |
| P3 | Calcolo waveform vettorizzato con numpy (eliminato loop Python frame-by-frame) | `video_generator.py` | Medio | ✅ Done |
| P4 | Font header + size-negotiation pre-computati (`_precompute_header`) | `video_generator.py` | Alto | ✅ Done |
| P5 | Font transcript + style + posizione pre-computati (`_precompute_transcript`) | `video_generator.py` | Alto | ✅ Done |
| P6 | Audio caricato una volta per episodio (`load_audio` + `loaded_audio` passato ai soundbite) | `audio_utils.py`, `cli.py` | Alto | ✅ Done |
| P7 | Rendering formati in parallelo con `concurrent.futures.ProcessPoolExecutor` | `cli.py` | Alto | ⬜ Todo |
| P8 | PIL images non chiuse in `_draw_rounded_box_with_shadow` (memory leak su run lunghi) | `video_generator.py` | Basso | ⬜ Todo |

### Dettaglio P7 — Rendering parallelo

Oggi in `_process_single_soundbite()` i formati sono renderizzati in sequenza:

```python
for format_name, format_desc in formats_info.items():
    generate_audiogram(...)  # bloccante
```

Con `ProcessPoolExecutor` i 3 formati (vertical, square, horizontal) girerebbero in parallelo,
riducendo il tempo totale da `N×T` a circa `T`.

Attenzione: MoviePy e PIL rilasciano il GIL durante l'encoding, quindi `ProcessPoolExecutor`
è preferibile a `ThreadPoolExecutor` per evitare contesa. Passare solo dati serializzabili
(no oggetti PIL già aperti — logo_img e loaded_audio vanno ricostruiti nel worker).

---

## Qualità del Codice

| # | Fix | File | Priorità | Stato |
|---|-----|------|----------|-------|
| C1 | `except Exception: pass` → log warning con contesto | `cli.py` | Alta | ✅ Done |
| C2 | `download_image()` duplicata rimossa da `video_generator.py` (usare `services/assets.py`) | `video_generator.py` | Alta | ✅ Done |
| C3 | `_SAVED_SEGMENTS = set()` rimosso (dead code, mai letto) | `video_generator.py` | Bassa | ✅ Done |
| C4 | `librosa` rimosso da `setup.py` (non usato, non in `requirements.txt`) | `setup.py` | Alta | ✅ Done |
| C5 | `requests` rimosso da `requirements.txt` (non importato direttamente) | `requirements.txt` | Bassa | ✅ Done |
| C6 | Percorsi font hard-coded macOS → ricerca cross-platform o config obbligatoria | `video_generator.py` | Media | ✅ Done |
| C7 | `print()` → `logging` strutturato con `FileHandler` (log su file + console) | entrambi | Media | ✅ Done |
| C8 | `_ffmpeg_warned` globale → incapsulato o rimosso | `cli.py` | Bassa | ⬜ Todo |
| C9 | Type hints aggiunti a `cli.py` e `video_generator.py` + mypy abilitato su entrambi | entrambi | Bassa | ⬜ Todo |
| C10 | SSL disabilitato → flag `verify_ssl` configurabile in `config.yaml` con warning | tutti i servizi | Media | ⬜ Todo |

### Dettaglio C1 — Eccezioni silenziose

```python
# Prima (cli.py)
except Exception:
    pass

# Dopo
except Exception as e:
    logging.warning("Could not load transcript chunks: %s", e)
```

### Dettaglio C2 — `download_image` duplicata

Rimuovere la funzione a `video_generator.py:213` e importare da `services/assets.py`:

```python
from .services.assets import download_image
```

### Dettaglio C7 — Logging strutturato con file

Configurare un logger unico in `__init__.py` con due handler: `StreamHandler` (console, livello INFO)
e `FileHandler` (file `audiogram_generator.log`, livello DEBUG). Sostituire tutti i `print()` con
chiamate al logger usando i livelli appropriati:

- `logging.info()` — progresso normale (download, rendering, ✓ completato)
- `logging.warning()` — situazioni degraded (audio mancante, font fallback, SSL disabilitato)
- `logging.debug()` — dettagli tecnici (dimensioni frame, waveform samples, percorsi file)
- `logging.error()` — errori non fatali con contesto dell'eccezione

Il log su file permette di diagnosticare run non presidiati (batch su più episodi).

### Dettaglio C6 — Font cross-platform

```python
import sys
_DEFAULT_FONT_PATHS = {
    "darwin": "/System/Library/Fonts/Helvetica.ttc",
    "linux":  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "win32":  "C:/Windows/Fonts/Arial.ttf",
}
DEFAULT_FONT_PATH = _DEFAULT_FONT_PATHS.get(sys.platform, "")
```

---

## Architettura (Long-term)

| # | Fix | Impatto | Stato |
|---|-----|---------|-------|
| A1 | Suddividere `video_generator.py` (809 righe) in moduli: `waveform.py`, `compositor.py`, `layouts.py`, `encoder.py` | Manutenibilità | ⬜ Todo |
| A2 | Estrarre logica di business da `cli.py` (763 righe) in un layer separato | Manutenibilità | ⬜ Todo |
| A3 | Test smoke del rendering (frame 64×64 senza audio reale) per coprire casi font mancanti ecc. | Qualità test | ⬜ Todo |
| A4 | Separare il layer interattivo da `process_one_episode()`: estrarre i prompt `input()` in una funzione dedicata in modo che la logica di orchestrazione sia testabile senza stdin | Testabilità | ⬜ Todo |

### Dettaglio A4 — Layer interattivo separato

Oggi `process_one_episode()` mescola orchestrazione, download, e prompt interattivi (`input()`),
rendendo impossibile testare il flusso senza simulare stdin. La soluzione è raccogliere tutte le
scelte dell'utente prima di chiamare la logica di business:

```
cli.py
  main()
    → _collect_user_choices(args, episodes) → UserChoices (dataclass)
    → process_one_episode(choices, ...)     ← zero input() qui dentro
```

Questo allinea anche con A2 e rende il layer interattivo sostituibile (es. future GUI o API).

---

## Test mancanti

I test esistono per config, RSS, transcript, captions, assets, selections e flow CLI in dry-run.
Mancano coperture per le seguenti aree.

| # | Test | File da creare/aggiornare | Priorità | Stato |
|---|------|---------------------------|----------|-------|
| T1 | `load_audio()` — verifica che restituisca un oggetto compatibile con `extract_audio_segment` | `test_audio_utils.py` (nuovo) | Alta | ✅ Done |
| T2 | `extract_audio_segment()` con `audio=` pre-caricato — verifica che non rilegga il file | `test_audio_utils.py` (nuovo) | Alta | ✅ Done |
| T3 | `extract_audio_segment()` senza `audio=` — verifica comportamento originale invariato | `test_audio_utils.py` (nuovo) | Alta | ✅ Done |
| T4 | `_resolve_header_text()` — tutti i valori di `header_title_source` (auto, podcast, episode, soundbite, none) | `test_video_generator.py` (nuovo) | Media | ✅ Done |
| T5 | `_precompute_header()` — verifica che ritorni font e lines coerenti con il testo di input | `test_video_generator.py` (nuovo) | Media | ✅ Done |
| T6 | `_precompute_transcript()` — verifica font, style e transcript_y per i 3 layout | `test_video_generator.py` (nuovo) | Media | ✅ Done |
| T7 | `get_waveform_data()` — verifica output vettorizzato: lunghezza array = `int(duration * fps)` | `test_video_generator.py` (nuovo) | Alta | ✅ Done |
| T8 | `_render_logo()` con `logo_img=None` — verifica che non sollevi eccezioni | `test_video_generator.py` (nuovo) | Bassa | ✅ Done |
| T9 | `process_one_episode()` con `loaded_audio` pre-caricato — verifica che `extract_audio_segment` non rilegga il file | `test_cli_flow.py` | Alta | ✅ Done |
| T10 | Smoke test rendering: generare un frame 64×64 con dati minimali e verificare shape array numpy | `test_video_generator.py` (nuovo) | Media | ✅ Done |
| T11 | `_process_single_soundbite()` — verifica che `loaded_audio` venga passato a `extract_audio_segment` | `test_cli_helpers.py` | Alta | ✅ Done |

### Note sui test

- **T1–T3** (`audio_utils`): mockare `AudioSegment.from_file` per non richiedere FFmpeg.
- **T4–T8, T10** (`video_generator`): mockare `ImageFont.truetype` e `Image.open` per non richiedere font/immagini reali; per T10 usare `Image.new('RGB', (64,64))` come logo fittizio.
- **T9, T11** (`cli`): usare `unittest.mock.patch` su `extract_audio_segment` e verificare il kwarg `audio=`.

---

## Nuove Funzionalità

| # | Funzionalità | File coinvolti | Stato |
|---|--------------|----------------|-------|
| F1 | Video audiogram per l'intero episodio (opzionale, flag `--full-episode`) | `cli.py`, `audio_utils.py`, `rendering/facade.py` | ⬜ Todo |

### Dettaglio F1 — Video episodio intero

Aggiungere la possibilità di generare un audiogram per l'intero episodio, senza selezionare un
soundbite. Attivabile con `--full-episode` da CLI o `full_episode: true` in `config.yaml`.

**Differenze rispetto al flusso soundbite:**

| Aspetto | Soundbite | Episodio intero |
|---------|-----------|-----------------|
| Audio | segmento estratto | file completo (no estrazione) |
| Transcript | chunk nella finestra start÷end | tutti i chunk |
| Titolo header | soundbite title o episode title | episode title |
| Nome output | `ep{N}_sb{M}_{format}.mp4` | `ep{N}_full_{format}.mp4` |
| Caption file | sì | opzionale |

**Punti di attenzione:**
- L'audio completo può essere lungo (30–90 min): il rendering sarà proporzionalmente lento.
  Considerare un warning esplicito sulla durata stimata prima di avviare.
- `get_waveform_data()` e il pre-load del logo già scalano con la durata; nessuna modifica necessaria.
- Il `loaded_audio` pre-caricato in `process_one_episode()` può essere riutilizzato direttamente,
  evitando una seconda lettura del file.
- La funzione `generate_audiogram()` accetta già `duration` come parametro: passare
  `len(audio) / 1000.0` dall'oggetto `AudioSegment` già in memoria.

---

## Documentazione

| # | Intervento | Priorità | Stato |
|---|------------|----------|-------|
| D1 | README: correggere nome venv da `.venv` a `venv` nel Quick Start | Alta | N/A — README già usa `.venv` |
| D2 | README: aggiornare sezione "Running tests" con il comando corretto `.venv/bin/python -m pytest tests/ -v` | Alta | ✅ Done |
| D3 | README: aggiungere sezione per la feature F1 (video episodio intero) quando implementata | Bassa | ⬜ Todo |
| D4 | README: non aggiornare per le migliorie interne (performance, refactoring) — sono dettagli implementativi non rilevanti per l'utente | — | N/A |

> **Valutazione:** il README è ben scritto e completo. Gli unici aggiornamenti necessari ora
> sono D1 e D2 (discrepanze concrete che possono bloccare un nuovo utente). D3 va fatto solo
> quando F1 è implementata. Non serve altro.

---

## Legenda

- ✅ **Done** — implementato e pronto per test
- ⬜ **Todo** — da implementare
