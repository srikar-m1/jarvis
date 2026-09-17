from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from jarvis.storage import SQLiteStore
from jarvis.tools import default_registry

DEFAULT_SYSTEM_PROMPT = (
    "You are Jarvis, Srikar's local personal assistant. "
    "Be concise, practical, witty when appropriate, and honest about uncertainty. "
    "Never claim that you performed an action unless the program confirms it."
)


class JarvisError(RuntimeError):
    """An expected, user-facing Jarvis error."""


@dataclass
class Settings:
    model: str = "llama3.2:3b"
    whisper_model: str = "tiny.en"
    voice: str = "Daniel"
    sample_rate: int = 16_000
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    database_path: Path = Path("~/.jarvis/jarvis.db").expanduser()

    @classmethod
    def from_environment(cls) -> Settings:
        return cls(
            model=os.getenv("JARVIS_MODEL", cls.model),
            whisper_model=os.getenv("JARVIS_WHISPER_MODEL", cls.whisper_model),
            voice=os.getenv("JARVIS_VOICE", cls.voice),
            database_path=Path(os.getenv("JARVIS_DB_PATH", str(cls.database_path))).expanduser(),
        )


@dataclass
class Conversation:
    system_prompt: str
    max_turns: int = 8
    messages: list[dict[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.messages:
            self.messages.append({"role": "system", "content": self.system_prompt})

    def add_user(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})
        self._trim()

    def add_assistant(self, text: str) -> None:
        self.messages.append({"role": "assistant", "content": text})
        self._trim()

    def _trim(self) -> None:
        # Keep the system prompt plus the most recent user/assistant turns.
        self.messages[:] = [self.messages[0], *self.messages[-(self.max_turns * 2) :]]


class OllamaBrain:
    def __init__(self, model: str) -> None:
        self.model = model

    def reply(self, messages: list[dict[str, str]]) -> str:
        try:
            import ollama
        except ImportError as exc:
            raise JarvisError(
                "The Ollama Python package is missing. Run: pip install -e ."
            ) from exc

        try:
            response: Any = ollama.chat(model=self.model, messages=messages)
        except Exception as exc:
            raise JarvisError(
                f"Could not reach model '{self.model}'. Make sure Ollama is running "
                f"and run: ollama pull {self.model}"
            ) from exc

        message = getattr(response, "message", None)
        content = getattr(message, "content", None)
        if content is None:
            try:
                content = response["message"]["content"]
            except (KeyError, TypeError):
                content = None

        if not content or not str(content).strip():
            raise JarvisError("Ollama returned an empty response.")
        return str(content).strip()


class MacSpeaker:
    def __init__(self, voice: str) -> None:
        self.voice = voice

    def speak(self, text: str) -> None:
        try:
            # Argument-list execution avoids shell injection and handles quotes safely.
            subprocess.run(
                ["say", "-v", self.voice, text],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError as exc:
            raise JarvisError("macOS text-to-speech command 'say' was not found.") from exc
        except subprocess.CalledProcessError as exc:
            raise JarvisError(
                f"macOS could not use the voice '{self.voice}'. "
                "Run 'say -v ?' to list installed voices."
            ) from exc


class WhisperListener:
    def __init__(self, model_name: str, sample_rate: int) -> None:
        self.model_name = model_name
        self.sample_rate = sample_rate
        self._model: Any = None

    def _load_dependencies(self) -> tuple[Any, Any]:
        try:
            import numpy as np
            import sounddevice as sd
            import whisper
        except ImportError as exc:
            raise JarvisError(
                "Voice dependencies are missing. Run: pip install -e '.[voice]'"
            ) from exc

        if self._model is None:
            print(f"Loading Whisper model '{self.model_name}' (first run may download it)...")
            self._model = whisper.load_model(self.model_name)
        return np, sd

    def listen(self) -> str:
        np, sd = self._load_dependencies()
        chunks: list[Any] = []

        def capture(indata: Any, frames: int, time: Any, status: Any) -> None:
            del frames, time
            if status:
                print(f"Microphone notice: {status}", file=sys.stderr)
            chunks.append(indata.copy())

        print("Press Enter to start speaking.")
        input()
        print("Listening... press Enter when finished.")
        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                callback=capture,
            ):
                input()
        except Exception as exc:
            raise JarvisError(
                "Could not access the microphone. Allow microphone access for Terminal "
                "in System Settings → Privacy & Security → Microphone."
            ) from exc

        if not chunks:
            raise JarvisError("No microphone audio was captured.")

        audio = np.concatenate(chunks, axis=0).reshape(-1)
        result = self._model.transcribe(audio, fp16=False, language="en")
        return str(result.get("text", "")).strip()


class Jarvis:
    def __init__(
        self,
        settings: Settings,
        brain: Any | None = None,
        speaker: Any | None = None,
        listener: Any | None = None,
    ) -> None:
        self.settings = settings
        self.brain = brain or OllamaBrain(settings.model)
        self.speaker = speaker or MacSpeaker(settings.voice)
        self.listener = listener or WhisperListener(settings.whisper_model, settings.sample_rate)
        self.conversation = Conversation(settings.system_prompt)

    def ask(self, prompt: str, speak: bool = True) -> str:
        prompt = prompt.strip()
        if not prompt:
            raise JarvisError("I did not hear a prompt.")

        self.conversation.add_user(prompt)
        answer = self.brain.reply(self.conversation.messages)
        self.conversation.add_assistant(answer)
        if speak:
            self.speaker.speak(answer)
        return answer

    def run_voice_loop(self, speak: bool = True) -> None:
        print("Jarvis is ready. Say 'goodbye' or 'exit' to stop.")
        while True:
            try:
                prompt = self.listener.listen()
                if not prompt:
                    print("I didn't catch that.")
                    continue
                print(f"You: {prompt}")
                if prompt.casefold().strip(" .!?") in {"exit", "quit", "goodbye"}:
                    print("Jarvis: Systems standing by.")
                    if speak:
                        self.speaker.speak("Systems standing by.")
                    return
                answer = self.ask(prompt, speak=speak)
                print(f"Jarvis: {answer}")
            except KeyboardInterrupt:
                print("\nJarvis: Systems standing by.")
                return
            except JarvisError as exc:
                print(f"Jarvis error: {exc}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jarvis", description="Local-first voice assistant for macOS"
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="Ask one text question. Omit it to start the microphone loop.",
    )
    parser.add_argument("--model", help="Ollama model name")
    parser.add_argument("--voice", help="macOS voice name")
    parser.add_argument("--whisper-model", help="Whisper model name")
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Print replies without speaking them",
    )
    local = parser.add_argument_group("local automation")
    local.add_argument("--remember", nargs=2, metavar=("KEY", "VALUE"))
    local.add_argument("--recall", metavar="KEY")
    local.add_argument("--list-notes", action="store_true")
    local.add_argument("--remind-in", nargs=2, metavar=("MINUTES", "MESSAGE"))
    local.add_argument("--list-reminders", action="store_true")
    local.add_argument("--due-reminders", action="store_true")
    local.add_argument("--complete-reminder", type=int, metavar="ID")
    local.add_argument("--system-status", action="store_true")
    return parser


def handle_local_command(args: argparse.Namespace, settings: Settings) -> bool:
    actions = (
        args.remember,
        args.recall,
        args.list_notes,
        args.remind_in,
        args.list_reminders,
        args.due_reminders,
        args.complete_reminder,
        args.system_status,
    )
    if not any(action is not None and action is not False for action in actions):
        return False

    store = SQLiteStore(settings.database_path)
    if args.remember:
        store.set_note(*args.remember)
        print(f"Remembered '{args.remember[0].strip().casefold()}'.")
    elif args.recall:
        value = store.get_note(args.recall)
        print(value if value is not None else "No note found.")
    elif args.list_notes:
        for key, value in store.list_notes():
            print(f"{key}: {value}")
    elif args.remind_in:
        try:
            minutes = int(args.remind_in[0])
        except ValueError as exc:
            raise JarvisError("Reminder minutes must be an integer.") from exc
        if minutes < 0:
            raise JarvisError("Reminder minutes cannot be negative.")
        due_at = datetime.now(UTC) + timedelta(minutes=minutes)
        reminder_id = store.add_reminder(args.remind_in[1], due_at)
        print(f"Reminder {reminder_id} scheduled for {due_at.isoformat()}.")
    elif args.list_reminders or args.due_reminders:
        due_before = datetime.now(UTC) if args.due_reminders else None
        reminders = store.list_reminders(due_before=due_before)
        for reminder in reminders:
            print(f"{reminder.id}: {reminder.due_at.isoformat()} - {reminder.message}")
    elif args.complete_reminder is not None:
        completed = store.complete_reminder(args.complete_reminder)
        print("Reminder completed." if completed else "Reminder not found.")
    elif args.system_status:
        status = default_registry().run("system_status")
        print(json.dumps(status, indent=2, sort_keys=True))
    return True


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_environment()
    if args.model:
        settings.model = args.model
    if args.voice:
        settings.voice = args.voice
    if args.whisper_model:
        settings.whisper_model = args.whisper_model

    try:
        if handle_local_command(args, settings):
            return 0
        assistant = Jarvis(settings)
        if args.prompt:
            answer = assistant.ask(args.prompt, speak=not args.silent)
            print(answer)
        else:
            assistant.run_voice_loop(speak=not args.silent)
    except JarvisError as exc:
        print(f"Jarvis error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nSystems standing by.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
