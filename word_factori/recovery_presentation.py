"""Fixed, safe player guidance. Raw errors belong only in diagnostic logs."""
from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryPresentation:
    code: str
    severity: str
    title: str
    action: str


def recovery_presentation(code: str, *, platform: str) -> RecoveryPresentation:
    installer = 'the Word Factori Linux installer' if platform.startswith('linux') else 'Install Word Factori Archipelago.cmd'
    messages = {
        'ready': ('info', 'Connected and ready', 'Keep the client open while playing.'),
        'disconnected': ('warning', 'Live updates unavailable', 'Keep the client open and reconnect to the same room. Displayed progress is last known.'),
        'auth_failed': ('error', 'Connection rejected', 'Check the room address, slot name and password in the regular client.'),
        'patch_missing': ('error', 'Game patch required', f'Close the game and run {installer} from the matching release.'),
        'patch_outdated': ('error', 'Game patch needs updating', f'Close the game and run {installer} from the matching release.'),
        'unsupported_build': ('error', 'Game build not supported', 'Stop installation. Use a supported game build or report its build identifier privately.'),
        'room_mismatch': ('error', 'Room and integration do not match', 'Install the release used to generate this room. Ask the host which release it requires.'),
        'save_unbound': ('warning', 'Choose this room\'s save', 'Select the Archipelago mod and enter this room\'s save. For a new room, select a fresh empty slot. Keep existing saves.'),
        'save_mismatch': ('error', 'Different save selected', 'Return to the save bound to this room. Keep your other saves unchanged.'),
        'mod_unselected': ('warning', 'Archipelago mod not selected', 'Select the Archipelago mod and this room\'s save in Word Factori.'),
        'native_waiting': ('warning', 'Waiting for the game', 'Keep the client open. Check that the Archipelago mod and matching game patch are active for this room.'),
        'mail_stale': ('warning', 'Mail display unavailable', 'Keep the client running. Reopen Mail or use the regular client; check that both came from the same release.'),
        'journal_invalid': ('error', 'Completion scanning paused', 'The save or completion journal could not be read safely. Preserve it and check diagnostics in the regular client.'),
        'unknown_error': ('error', 'Integration needs attention', 'Open the regular client for diagnostic details. Preserve your saves.'),
    }
    if code not in messages:
        code = 'unknown_error'
    return RecoveryPresentation(code, *messages[code])
