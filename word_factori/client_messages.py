"""Renderer-neutral, bounded Archipelago client messages."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Mapping


MAX_MESSAGE_TEXT = 4096
MAX_TRANSCRIPT_MESSAGES = 500


class ClientMessageKind(str, Enum):
    CHAT = "chat"
    HINT = "hint"
    SYSTEM = "system"
    COMMAND = "command"
    ERROR = "error"


def _bounded_text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("client message text cannot be blank")
    if len(value) <= MAX_MESSAGE_TEXT:
        return value
    return value[: MAX_MESSAGE_TEXT - 1] + "…"


def _sender_slot(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


@dataclass(frozen=True)
class ClientMessage:
    key: str
    kind: ClientMessageKind
    text: str
    sender_slot: int | None
    observed_at: str

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key.strip():
            raise ValueError("client message key cannot be blank")
        if not isinstance(self.kind, ClientMessageKind):
            raise ValueError("client message kind is invalid")
        if self.text != _bounded_text(self.text):
            raise ValueError("client message text is too long")
        if self.sender_slot != _sender_slot(self.sender_slot):
            raise ValueError("client message sender slot is invalid")
        if not isinstance(self.observed_at, str) or not self.observed_at.strip():
            raise ValueError("client message observed time cannot be blank")


@dataclass(frozen=True)
class ClientTranscript:
    messages: tuple[ClientMessage, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.messages, tuple):
            raise ValueError("client transcript messages must be immutable")
        if len(self.messages) > MAX_TRANSCRIPT_MESSAGES:
            raise ValueError("client transcript exceeds its history limit")
        if any(not isinstance(message, ClientMessage) for message in self.messages):
            raise ValueError("client transcript contains an invalid message")

    @classmethod
    def empty(cls) -> "ClientTranscript":
        return cls()


def _message_kind(packet_type: object) -> ClientMessageKind:
    if packet_type == "Chat":
        return ClientMessageKind.CHAT
    if packet_type == "Hint":
        return ClientMessageKind.HINT
    return ClientMessageKind.SYSTEM


def normalize_print_json(
    packet: object,
    rendered: str,
    observed_at: str,
    *,
    sequence: int,
) -> ClientMessage:
    """Normalize a standard PrintJSON packet without exposing raw protocol data."""

    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        raise ValueError("client message sequence is invalid")
    packet_mapping: Mapping[str, object] = packet if isinstance(packet, Mapping) else {}
    kind = _message_kind(packet_mapping.get("type"))
    text = _bounded_text(rendered)
    sender = _sender_slot(packet_mapping.get("slot"))
    if not isinstance(observed_at, str) or not observed_at.strip():
        raise ValueError("client message observed time cannot be blank")
    fingerprint = hashlib.sha256(
        f"{kind.value}\0{sender}\0{text}\0{observed_at}".encode("utf-8"),
    ).hexdigest()[:16]
    return ClientMessage(
        key=f"{kind.value}:{sequence}:{fingerprint}",
        kind=kind,
        text=text,
        sender_slot=sender,
        observed_at=observed_at,
    )


def append_message(transcript: ClientTranscript, message: ClientMessage) -> ClientTranscript:
    if not isinstance(transcript, ClientTranscript):
        raise ValueError("client transcript is invalid")
    if not isinstance(message, ClientMessage):
        raise ValueError("client message is invalid")
    messages = (transcript.messages + (message,))[-MAX_TRANSCRIPT_MESSAGES:]
    return ClientTranscript(messages)
