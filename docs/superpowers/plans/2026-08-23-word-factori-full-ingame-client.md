# Word Factori Full In-Game Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the accepted item-ledger overlay into a complete Word Factori-styled Archipelago client with connection, authentication, chat, commands, hints, errors, and keyboard-safe in-game operation.

**Architecture:** Extend the existing renderer-neutral protocol and presentation reducer rather than moving networking into the overlay. `WordFactoriContext` continues to call Archipelago's standard `connect`, `disconnect`, `ClientCommandProcessor`, `on_user_say`, and authentication paths; the Kivy child renders state and returns validated user intents over the existing private process pipe.

**Tech Stack:** Python 3.12+, Archipelago 0.6.7 `CommonClient`, item-ledger overlay components, standard-library process pipe, bundled Kivy/KivyMD, `unittest`.

**Spec:** `docs/superpowers/specs/2026-08-23-word-factori-ingame-client-design.md`

## Global Constraints

- Complete `docs/superpowers/plans/2026-08-23-word-factori-item-ledger-overlay.md` and its live acceptance gate first.
- Keep `WordFactoriContext` as the only Archipelago network peer.
- Never send server passwords, sockets, or raw protocol objects to the renderer child.
- Never take keyboard focus while the ledger is closed.
- Preserve URI launch, command semantics, reconnect behavior, logs, and the regular client fallback.
- Do not patch or redistribute Word Factori binaries, saves, fonts, icons, or sprites.
- Use TDD and a focused commit for every task.
- Treat each test function shown below as a method on the named `unittest.TestCase` or `unittest.IsolatedAsyncioTestCase` class in that test module, even when the surrounding class is omitted for brevity.
- Do not remove the experimental label until the final live acceptance task passes every required row.

---

## File map

- Create `word_factori/client_messages.py`: normalized chat, hint, connection, command-result, and error rows.
- Modify `word_factori/overlay_model.py`: Items/Chat views, connection form, password prompt, input focus, command feedback.
- Modify `word_factori/overlay_protocol.py`: validated full-client child actions and parent messages.
- Modify `word_factori/overlay_renderer.py`: chat list, text entry, connection sheet, password sheet, status/error views.
- Modify `word_factori/client.py`: intent routing to standard Archipelago connection/auth/command APIs and structured message capture.
- Modify `word_factori/overlay_supervisor.py`: sensitive-field rejection and full-client action delivery.
- Modify `tests/test_overlay_model.py`, `tests/test_overlay_supervisor.py`, `tests/test_client_lifecycle.py`: full-client unit and integration coverage.
- Create `tests/test_client_messages.py`: structured message parsing and bounded transcript behavior.
- Modify `README.md`, `word_factori/docs/setup_en.md`: full in-game client operation and fallback.
- Create `docs/testing/full-ingame-client-acceptance.md`: official-release acceptance evidence.

---

### Task 1: Full-Client Message Domain

**Files:**
- Create: `word_factori/client_messages.py`
- Create: `tests/test_client_messages.py`

**Interfaces:**
- Consumes: structured `PrintJSON` dictionaries and rendered fallback text from `CommonContext.jsontotextparser`.
- Produces: `ClientMessageKind`, `ClientMessage`, `ClientTranscript`, `normalize_print_json(...)`, and `append_message(...)`.

- [ ] **Step 1: Write failing tests for chat, hint, system, command result, and bounded history**

```python
class ClientMessageTests(unittest.TestCase):
    def test_chat_packet_preserves_structured_parts_and_sender(self):
        packet = {"type": "Chat", "slot": 2, "data": [{"text": "Alex: "}, {"text": "hello"}]}
        message = normalize_print_json(packet, rendered="Alex: hello", observed_at="now")
        self.assertIs(message.kind, ClientMessageKind.CHAT)
        self.assertEqual(message.sender_slot, 2)
        self.assertEqual(message.text, "Alex: hello")


    def test_transcript_keeps_latest_five_hundred_messages(self):
        transcript = ClientTranscript.empty()
        for index in range(505):
            transcript = append_message(transcript, make_message(index))
        self.assertEqual(len(transcript.messages), 500)
        self.assertEqual(transcript.messages[0].text, "5")
```

- [ ] **Step 2: Run the tests and confirm the module import fails**

Run: `python -m unittest tests.test_client_messages -v`

Expected: import failure.

- [ ] **Step 3: Implement immutable message values and normalization**

```python
class ClientMessageKind(str, Enum):
    CHAT = "chat"
    HINT = "hint"
    SYSTEM = "system"
    COMMAND = "command"
    ERROR = "error"

@dataclass(frozen=True)
class ClientMessage:
    key: str
    kind: ClientMessageKind
    text: str
    sender_slot: int | None
    observed_at: str

@dataclass(frozen=True)
class ClientTranscript:
    messages: tuple[ClientMessage, ...] = ()

    @classmethod
    def empty(cls) -> "ClientTranscript":
        return cls()
```

Map `Chat` to chat, `Hint` to hint, `Join`/`Part` and untyped notices to system, local command echo/output to command, and connection/auth/campaign/save errors to error. Generate an in-memory key from kind, packet fields, and a monotonic local sequence; the transcript is not persisted.

- [ ] **Step 4: Add validation tests for blank, oversized, and malformed messages**

Reject blank rendered text, truncate displayed text at 4096 Unicode code points with an ellipsis, and replace invalid sender slots with `None`. Preserve the standard file/stream logs independently.

- [ ] **Step 5: Run focused tests**

Run: `python -m unittest tests.test_client_messages -v`

Expected: all tests pass.

- [ ] **Step 6: Commit the message domain**

```powershell
git add word_factori/client_messages.py tests/test_client_messages.py
git commit -m "feat: normalize full-client messages"
```

---

### Task 2: Full-Client Presentation State and Protocol

**Files:**
- Modify: `word_factori/overlay_model.py`
- Modify: `word_factori/overlay_protocol.py`
- Modify: `tests/test_overlay_model.py`
- Modify: `tests/test_overlay_supervisor.py`

**Interfaces:**
- Consumes: `ClientTranscript` and the item-only overlay state.
- Produces: `OverlayView`, `ConnectionState`, `ConnectIntent`, `SubmitTextIntent`, `PasswordIntent`, and version-2 protocol messages.

- [ ] **Step 1: Write failing state tests for Items/Chat tabs and keyboard focus**

```python
def test_keyboard_focus_exists_only_in_open_chat_or_connection_sheet(self):
    state = OverlayState.closed()
    self.assertFalse(snapshot(state).accepts_keyboard)
    state = apply_action(state, OverlayAction("open-chat"))
    self.assertTrue(snapshot(state).accepts_keyboard)
    state = apply_action(state, OverlayAction("close"))
    self.assertFalse(snapshot(state).accepts_keyboard)
```

- [ ] **Step 2: Write failing tests for connection, password, submit, and validation intents**

```python
def test_protocol_accepts_bounded_connect_intent_and_rejects_password_in_snapshot(self):
    intent = decode_child_action(json.dumps({"version": 2, "type": "connect",
        "payload": {"address": "archipelago.gg:38281", "slot": "Factory", "password": "secret"}}))
    self.assertEqual(intent.address, "archipelago.gg:38281")
    with self.assertRaisesRegex(ValueError, "password"):
        encode_parent_message(ParentMessage("snapshot", {"password": "secret"}))
```

- [ ] **Step 3: Implement full-client states and actions**

```python
class OverlayView(str, Enum):
    ITEMS = "items"
    CHAT = "chat"
    CONNECT = "connect"
    PASSWORD = "password"

class ConnectionState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    AUTHENTICATING = "authenticating"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"
```

Add reducer actions `open-items`, `open-chat`, `open-connect`, `request-password`, `connection-state`, `submit-started`, and `submit-failed`. Closing always clears the renderer's input buffer and keyboard-focus flag.

- [ ] **Step 4: Upgrade the protocol with explicit child intent dataclasses**

```python
@dataclass(frozen=True)
class ConnectIntent:
    address: str
    slot: str
    password: str | None

@dataclass(frozen=True)
class SubmitTextIntent:
    text: str

@dataclass(frozen=True)
class PasswordIntent:
    password: str
```

Accept only `connect`, `disconnect`, `submit-text`, `submit-password`, and existing local UI actions. Limit address to 512 characters, slot to 64, password to 256, and submitted text to 4096. Never echo password values in exceptions or encoded parent messages.

- [ ] **Step 5: Add backward compatibility tests**

Confirm protocol version 1 snapshots/actions from the item-only implementation still decode. Version 2 is emitted only after both parent and child announce support during startup.

- [ ] **Step 6: Run model and supervisor tests**

Run: `python -m unittest tests.test_overlay_model tests.test_overlay_supervisor -v`

Expected: all tests pass.

- [ ] **Step 7: Commit presentation and protocol expansion**

```powershell
git add word_factori/overlay_model.py word_factori/overlay_protocol.py tests/test_overlay_model.py tests/test_overlay_supervisor.py
git commit -m "feat: add full-client overlay protocol"
```

---

### Task 3: Standard Archipelago Connection, Authentication, and Input Routing

**Files:**
- Modify: `word_factori/client.py`
- Modify: `tests/test_client_lifecycle.py`

**Interfaces:**
- Consumes: Task 2 intents and Archipelago `CommonContext.connect`, `disconnect`, `server_auth`, `console_input`, and `WordFactoriCommandProcessor`.
- Produces: `handle_overlay_intent(...)`, overlay-driven password/slot input, connection snapshots, and standard command/chat routing.

- [ ] **Step 1: Extend test doubles and write failing connect/disconnect tests**

```python
async def test_overlay_connect_uses_common_context_connection_path(self):
    await self.ctx.handle_overlay_intent(ConnectIntent("localhost:38281", "Factory", None))
    self.assertEqual(self.ctx.auth, "Factory")
    self.assertEqual(self.ctx.connect_calls, ["localhost:38281"])

async def test_overlay_disconnect_calls_common_disconnect(self):
    await self.ctx.handle_overlay_intent(DisconnectIntent())
    self.assertEqual(self.ctx.disconnect_calls, 1)
```

- [ ] **Step 2: Run the tests and confirm the intent handler is missing**

Run: `python -m unittest tests.test_client_lifecycle -v`

Expected: failures for `handle_overlay_intent`.

- [ ] **Step 3: Route connection intents through standard CommonContext methods**

```python
async def handle_overlay_intent(self, intent: OverlayIntent) -> None:
    if isinstance(intent, ConnectIntent):
        self.auth = intent.slot.strip()
        self.password = intent.password or None
        await self.connect(intent.address.strip())
    elif isinstance(intent, DisconnectIntent):
        await self.disconnect()
    elif isinstance(intent, SubmitTextIntent):
        self.command_processor(self)(intent.text)
    elif isinstance(intent, PasswordIntent):
        self.input_queue.put_nowait(intent.password)
```

Run this coroutine on the parent asyncio loop. Do not call network methods in the renderer or its pipe-polling thread.

- [ ] **Step 4: Write failing password-request tests**

```python
async def test_server_auth_requests_password_in_overlay_without_exposing_it(self):
    task = asyncio.create_task(self.ctx.server_auth(password_requested=True))
    await asyncio.sleep(0)
    self.assertIs(self.ctx.overlay_state.view, OverlayView.PASSWORD)
    await self.ctx.handle_overlay_intent(PasswordIntent("secret"))
    await task
    self.assertEqual(self.ctx.password, "secret")
    self.assertNotIn("secret", self.ctx.overlay.last_encoded_snapshot)
```

- [ ] **Step 5: Integrate `console_input()` with the overlay input queue**

When the overlay is healthy, `get_username()` and `server_auth()` publish slot/password prompts and await `self.input_queue`. When unavailable, delegate to `super().get_username()` and `super().server_auth(password_requested)` so CLI/generic GUI fallback remains intact.

- [ ] **Step 6: Write failing chat and command-routing tests**

```python
async def test_plain_text_uses_say_and_slash_command_uses_processor(self):
    await self.ctx.handle_overlay_intent(SubmitTextIntent("hello team"))
    await asyncio.sleep(0)
    self.assertIn({"cmd": "Say", "text": "hello team"}, self.ctx.sent_messages)
    await self.ctx.handle_overlay_intent(SubmitTextIntent("/wf_status"))
    self.assertEqual(self.ctx.command_inputs[-1], "/wf_status")
```

Use `WordFactoriCommandProcessor(self)(text)` for every submitted line so plain chat, `!server` commands, and `/local` commands retain CommonClient semantics. Call `on_ui_command(text)` only for non-secret command echo.

- [ ] **Step 7: Publish connection state without credentials**

Map connect attempt, `RoomInfo`, `Connected`, `ConnectionRefused`, disconnect, and autoreconnect events to `ConnectionState`. Publish server host, slot display name, and errors; never publish password, URI userinfo, auth tokens, or raw exception representations containing credentials.

- [ ] **Step 8: Run lifecycle and existing tests**

Run: `python -m unittest tests.test_client_lifecycle tests.test_core -v`

Expected: all tests pass.

- [ ] **Step 9: Commit parent-side full-client routing**

```powershell
git add word_factori/client.py tests/test_client_lifecycle.py
git commit -m "feat: route in-game client connection and input"
```

---

### Task 4: Chat, Hints, Commands, and Error Presentation

**Files:**
- Modify: `word_factori/client.py`
- Modify: `word_factori/overlay_model.py`
- Modify: `tests/test_client_lifecycle.py`
- Modify: `tests/test_client_messages.py`

**Interfaces:**
- Consumes: Task 1 message normalizer and Task 3 input routing.
- Produces: complete renderer-neutral transcript and error/status snapshots.

- [ ] **Step 1: Write failing structured `PrintJSON` capture tests**

```python
def test_print_json_reaches_standard_log_and_overlay_transcript(self):
    packet = {"type": "Chat", "slot": 2, "data": [{"text": "Alex: hello"}]}
    self.ctx.on_print_json(packet)
    self.assertEqual(self.ctx.standard_print_calls, [packet])
    self.assertIs(self.ctx.transcript.messages[-1].kind, ClientMessageKind.CHAT)
```

- [ ] **Step 2: Preserve `super().on_print_json` and append normalized messages**

```python
def on_print_json(self, args: dict) -> None:
    super().on_print_json(args)
    rendered = self.jsontotextparser(copy.deepcopy(args.get("data", [])))
    message = normalize_print_json(args, rendered, utc_now())
    self.transcript = append_message(self.transcript, message)
    self.publish_overlay()
    self.record_item_send_if_relevant(args)
```

Ensure the item-only send handler runs once and an `ItemSend` can appear in the item ledger without being duplicated in chat unless the player enables system messages.

- [ ] **Step 3: Write failing command-output capture tests**

Override `WordFactoriCommandProcessor.output` to call `super().output(text)` and `ctx.record_command_output(text)`. Confirm `/wf_status`, `/received`, invalid commands, and hint results appear in the Chat view with `ClientMessageKind.COMMAND`.

- [ ] **Step 4: Normalize safe errors into actionable cards**

Map campaign mismatch, save-slot mismatch, mod not selected, overlay fallback, connection refused, password required, and version mismatch to stable error codes plus player-facing text. The renderer receives code/text, never exception objects.

```python
@dataclass(frozen=True)
class ClientNotice:
    code: str
    severity: str
    text: str
    action: str | None = None
```

- [ ] **Step 5: Add hint and system-message filtering tests**

The Chat view defaults to chat, hints, commands, and errors. Join/part spam is hidden by default but can be enabled in settings. Unrelated `ItemSend` packets remain excluded.

- [ ] **Step 6: Run full non-GUI tests**

Run: `python -m unittest tests.test_client_messages tests.test_client_lifecycle tests.test_overlay_model -v`

Expected: all tests pass.

- [ ] **Step 7: Commit message and error integration**

```powershell
git add word_factori/client.py word_factori/overlay_model.py tests/test_client_lifecycle.py tests/test_client_messages.py
git commit -m "feat: present Archipelago chat and client notices"
```

---

### Task 5: Full Word Factori-Styled Renderer

**Files:**
- Modify: `word_factori/overlay_renderer.py`
- Modify: `tests/test_overlay_model.py`
- Modify: `tests/test_window_tracker.py`

**Interfaces:**
- Consumes: full snapshots and child intents from Tasks 2-4.
- Produces: Items/Chat navigation, connection and password sheets, text entry, status/error cards, and keyboard-safe interaction.

- [ ] **Step 1: Add renderer-independent layout contract tests**

```python
def test_full_snapshot_has_items_chat_status_and_focus_contract(self):
    view = snapshot(make_connected_chat_state())
    self.assertEqual(view.tabs, ("items", "chat"))
    self.assertEqual(view.active_view, "chat")
    self.assertTrue(view.accepts_keyboard)
    self.assertEqual(view.connection_state, "connected")
```

- [ ] **Step 2: Implement focused Kivy widget units**

Add `ClientTabs`, `ChatTranscript`, `ChatComposer`, `ConnectionSheet`, `PasswordSheet`, and `ClientNoticeCard`. Reuse `MailboxButton`, `DeliveryToast`, `DispatchLedger`, font registration, color tokens, and window tracking from the item-only renderer.

The Chat composer has one text input and one send button. `Enter` submits, `Shift+Enter` inserts a newline, `Escape` clears focus and closes the ledger, and passwords use a masked field.

- [ ] **Step 3: Implement explicit focus and click-through transitions**

```python
def set_interactive(self, enabled: bool) -> None:
    self._set_hit_test_regions(self.interactive_rectangles() if enabled else self.mailbox_rectangles())
    if not enabled:
        self.chat_input.focus = False
        self.password_input.focus = False
```

Only an open connection/password/chat sheet accepts keyboard input. Alt-tab, game focus loss, `F8`, `Escape`, or close removes focus and clears unsubmitted password text.

- [ ] **Step 4: Add visual handling for disconnected and reconnecting states**

Disconnected shows address and slot fields. Connecting/authenticating disables duplicate submission. Reconnecting shows attempt status and a Disconnect button. Connected collapses the form into a green status indicator. Errors remain visible until dismissed or replaced by a successful state.

- [ ] **Step 5: Run automated tests and the frozen-runtime UI probe**

```powershell
python -m unittest tests.test_overlay_model tests.test_window_tracker -v
```

Then verify in the installed Archipelago runtime: connect form, URI autoconnect, password prompt, Chat/Items switch, input focus, `Enter`, `Shift+Enter`, `Escape`, `F8`, alt-tab, scaling, and regular-client fallback. Add the results to `docs/testing/full-ingame-client-acceptance.md` as preliminary evidence.

- [ ] **Step 6: Commit the full renderer**

```powershell
git add word_factori/overlay_renderer.py tests/test_overlay_model.py tests/test_window_tracker.py docs/testing/full-ingame-client-acceptance.md
git commit -m "feat: render full in-game Archipelago client"
```

---

### Task 6: Official-Release Documentation and Acceptance Gate

**Files:**
- Modify: `README.md`
- Modify: `word_factori/docs/setup_en.md`
- Modify: `tools/verify_release.py`
- Modify: `tests/test_publication.py`
- Modify: `docs/testing/full-ingame-client-acceptance.md`

**Interfaces:**
- Consumes: complete full in-game client.
- Produces: verified user instructions, release gate evidence, and an explicit decision on the experimental label.

- [ ] **Step 1: Write failing documentation/publication assertions**

Add tests that README and setup documentation contain the single-install flow, mailbox/F8 controls, Items/Chat behavior, connection/password flow, supported display modes, fallback instructions, and no claim of official status before acceptance is marked PASS.

- [ ] **Step 2: Update player documentation**

Lead with:

1. install once;
2. launch Word Factori Client;
3. start Word Factori;
4. connect from the in-game ledger or use an `archipelago://` URI;
5. press `F8` for Items, Chat, hints, commands, and connection status.

Keep the generic client fallback and `/wf_overlay restart` troubleshooting visible. Do not require users to start a second overlay program.

- [ ] **Step 3: Complete automated release verification**

Make `verify_release.py` import every new pure module outside Kivy, inspect the APWorld for all renderer/client files, and continue rejecting proprietary fonts, binaries, saves, generated rooms, secrets, and `.superpowers` session artifacts.

- [ ] **Step 4: Execute the complete live acceptance matrix**

Use a fresh two-player room and test:

- URI and manual connection;
- no-password and password-protected rooms;
- invalid address, invalid slot, wrong game, wrong password, and version mismatch;
- automatic reconnect and intentional disconnect;
- chat send/receive and echoed local chat;
- `!hint`, `!remaining`, `/wf_status`, `/received`, and invalid commands;
- items sent, received, self, historical backfill, and room switching;
- campaign mismatch, mod not selected, and save-slot mismatch notices;
- all item-overlay display, scaling, focus, multi-monitor, and renderer-crash rows;
- complete play without the generic client visible.

Record PASS/FAIL and evidence for every row. Do not leave a blank or `not tested` row.

- [ ] **Step 5: Run final tests, build, archive verification, and clean-tree checks**

```powershell
python -m unittest discover -s tests -v
python tools\build_release.py
python tools\verify_release.py
git diff --check
git status --short
```

Expected: all tests pass, release verification passes, and only the completed acceptance/documentation changes are pending.

- [ ] **Step 6: Decide the release label from evidence**

If every required acceptance row passes, update README from `experimental` to `release candidate` and document supported Windows/display boundaries. If any row fails, retain `experimental`, document the exact observed limitation, and keep the official-release gate closed.

- [ ] **Step 7: Re-run verification after the label decision**

Repeat the full commands from Step 5. The outcome must remain green after documentation changes.

- [ ] **Step 8: Commit official-release acceptance**

```powershell
git add README.md word_factori/docs/setup_en.md tools/verify_release.py tests/test_publication.py docs/testing/full-ingame-client-acceptance.md
git commit -m "test: verify full in-game client release gate"
```
