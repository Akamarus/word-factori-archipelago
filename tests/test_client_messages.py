import unittest

from word_factori.client_messages import (
    ClientMessage,
    ClientMessageKind,
    ClientTranscript,
    append_message,
    normalize_print_json,
)


class ClientMessageTests(unittest.TestCase):
    def test_chat_packet_preserves_rendered_text_and_sender(self):
        packet = {
            "type": "Chat",
            "slot": 2,
            "data": [{"text": "Alex: "}, {"text": "hello"}],
        }

        message = normalize_print_json(
            packet, rendered="Alex: hello", observed_at="now", sequence=7,
        )

        self.assertIs(message.kind, ClientMessageKind.CHAT)
        self.assertEqual(2, message.sender_slot)
        self.assertEqual("Alex: hello", message.text)
        self.assertIn(":7:", message.key)

    def test_packet_kinds_are_normalized_without_raw_protocol_values(self):
        cases = {
            "Hint": ClientMessageKind.HINT,
            "Join": ClientMessageKind.SYSTEM,
            "Part": ClientMessageKind.SYSTEM,
            "ItemSend": ClientMessageKind.SYSTEM,
            None: ClientMessageKind.SYSTEM,
        }

        for packet_type, expected in cases.items():
            with self.subTest(packet_type=packet_type):
                packet = {"data": [{"text": "notice"}]}
                if packet_type is not None:
                    packet["type"] = packet_type
                message = normalize_print_json(
                    packet, rendered="notice", observed_at="now", sequence=0,
                )
                self.assertIs(expected, message.kind)

    def test_transcript_keeps_latest_five_hundred_messages(self):
        transcript = ClientTranscript.empty()
        for index in range(505):
            transcript = append_message(transcript, self.make_message(index))

        self.assertEqual(500, len(transcript.messages))
        self.assertEqual("5", transcript.messages[0].text)
        self.assertEqual("504", transcript.messages[-1].text)

    def test_blank_message_is_rejected_and_long_text_is_bounded(self):
        with self.assertRaisesRegex(ValueError, "blank"):
            normalize_print_json({}, rendered="  ", observed_at="now", sequence=0)

        message = normalize_print_json(
            {}, rendered="x" * 5000, observed_at="now", sequence=0,
        )
        self.assertEqual(4096, len(message.text))
        self.assertTrue(message.text.endswith("…"))

    def test_invalid_sender_and_packet_shape_are_contained(self):
        for sender in (True, -1, "2", [], None):
            with self.subTest(sender=sender):
                message = normalize_print_json(
                    {"type": "Chat", "slot": sender},
                    rendered="hello",
                    observed_at="now",
                    sequence=0,
                )
                self.assertIsNone(message.sender_slot)

        message = normalize_print_json(
            "not a packet", rendered="fallback", observed_at="now", sequence=0,
        )
        self.assertIs(ClientMessageKind.SYSTEM, message.kind)

    def test_values_are_immutable_and_validate_direct_construction(self):
        message = self.make_message(1)
        with self.assertRaises((AttributeError, TypeError)):
            message.text = "changed"
        with self.assertRaisesRegex(ValueError, "key"):
            ClientMessage("", ClientMessageKind.CHAT, "hello", None, "now")
        with self.assertRaisesRegex(ValueError, "observed"):
            ClientMessage("key", ClientMessageKind.CHAT, "hello", None, "")

    @staticmethod
    def make_message(index: int) -> ClientMessage:
        return ClientMessage(
            key=f"system:{index}",
            kind=ClientMessageKind.SYSTEM,
            text=str(index),
            sender_slot=None,
            observed_at="now",
        )


if __name__ == "__main__":
    unittest.main()
