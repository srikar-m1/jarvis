import unittest

from jarvis.app import Conversation, Jarvis, JarvisError, Settings


class FakeBrain:
    def __init__(self, answer: str = "Systems online.") -> None:
        self.answer = answer
        self.messages = []

    def reply(self, messages):
        self.messages = list(messages)
        return self.answer


class FakeSpeaker:
    def __init__(self) -> None:
        self.spoken = []

    def speak(self, text):
        self.spoken.append(text)


class JarvisTests(unittest.TestCase):
    def test_ask_tracks_conversation_and_speaks(self):
        brain = FakeBrain()
        speaker = FakeSpeaker()
        assistant = Jarvis(Settings(), brain=brain, speaker=speaker)

        result = assistant.ask("Jarvis, check in.")

        self.assertEqual(result, "Systems online.")
        self.assertEqual(
            brain.messages[-1],
            {"role": "user", "content": "Jarvis, check in."},
        )
        self.assertEqual(
            assistant.conversation.messages[-1],
            {"role": "assistant", "content": "Systems online."},
        )
        self.assertEqual(speaker.spoken, ["Systems online."])

    def test_silent_ask_does_not_speak(self):
        speaker = FakeSpeaker()
        assistant = Jarvis(Settings(), brain=FakeBrain(), speaker=speaker)

        assistant.ask("Check in.", speak=False)

        self.assertEqual(speaker.spoken, [])

    def test_empty_prompt_is_rejected(self):
        assistant = Jarvis(Settings(), brain=FakeBrain(), speaker=FakeSpeaker())

        with self.assertRaisesRegex(JarvisError, "did not hear"):
            assistant.ask("   ")

    def test_conversation_keeps_recent_turns(self):
        conversation = Conversation("system", max_turns=2)
        for index in range(4):
            conversation.add_user(f"question {index}")
            conversation.add_assistant(f"answer {index}")

        self.assertEqual(
            conversation.messages[0],
            {"role": "system", "content": "system"},
        )
        self.assertEqual(len(conversation.messages), 5)
        self.assertEqual(conversation.messages[1]["content"], "question 2")


if __name__ == "__main__":
    unittest.main()
