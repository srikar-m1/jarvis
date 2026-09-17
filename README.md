# Jarvis

A local-first Python assistant for macOS with voice input, Ollama conversations, SQLite notes and reminders, and explicitly allowlisted automation tools:

`microphone → Whisper → Ollama → macOS speech`

Voice mode is intentionally push-to-talk, so the microphone is never left open in the background. Notes, reminders, and system status work without Ollama or the optional voice dependencies.

## Local automation

```bash
jarvis --remember role "Python backend developer"
jarvis --recall role
jarvis --list-notes
jarvis --remind-in 30 "Send the referral application"
jarvis --list-reminders
jarvis --due-reminders
jarvis --complete-reminder 1
jarvis --system-status
```

Data is stored in `~/.jarvis/jarvis.db`. Set `JARVIS_DB_PATH` to use another location.

## What this Mac needs

This machine already has Apple Silicon, Python 3.12, Homebrew, and the macOS
`say` command. Ollama is not installed yet.

## 1. Install Ollama

```bash
brew install ollama
brew services start ollama
ollama pull llama3.2:3b
```

You can stop the background service later with:

```bash
brew services stop ollama
```

## 2. Create the Python environment

From this project directory:

```bash
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[voice]"
```

The first Whisper run will download the selected speech model.

Run the dependency-free tests with:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

For linting and coverage:

```bash
python -m pip install -e ".[dev]"
ruff check src tests
coverage run -m unittest discover -s tests -v
coverage report
```

## 3. Test the brain before the microphone

```bash
jarvis --silent "Jarvis, check in."
```

Remove `--silent` when you want the reply spoken aloud:

```bash
jarvis "Jarvis, check in."
```

## 4. Start voice mode

```bash
jarvis
```

Press Enter, speak, and press Enter again. Say “goodbye” to stop.

macOS may ask for microphone permission. If recording fails, enable it for
Terminal under **System Settings → Privacy & Security → Microphone**.

## Options

```bash
jarvis --model qwen3:8b
jarvis --voice Samantha
jarvis --whisper-model base.en
say -v "?"
```

The same defaults can be set with `JARVIS_MODEL`, `JARVIS_VOICE`, and
`JARVIS_WHISPER_MODEL`.

## Architecture

- `app.py` coordinates CLI, text, and voice modes.
- `storage.py` owns SQLite notes and reminders.
- `tools.py` exposes a small allowlisted tool registry.
- Ollama and Whisper are loaded only when conversation or voice features need them.

GitHub Actions runs linting, unit tests, and a 70% coverage gate on every pull request.

## Safety boundary

Jarvis cannot execute model-generated terminal commands. Local tools are explicit Python functions registered by name, and unknown tools are rejected.
