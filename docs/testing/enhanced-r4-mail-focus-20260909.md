# Enhanced r4 client: Chat to Items focus handoff

Jack reported that clicking Items from Chat made AP Mail disappear. The
renderer determined visibility from the *new* snapshot's keyboard permission,
while the overlay still owned foreground focus from Chat. It hid the panel and
passed `game_active=False` to the native hook, preventing the hook from returning
focus to the game. This is separate from passive mouse activation handled in r3.

Visibility now follows actual game/overlay focus, independently of the selected
tab's keyboard policy. The existing hook can return focus on Chat to Items before
the next sample. Hidden/minimized games and focus on unrelated windows still hide
the overlay without taking foreground focus back.

The regression executes the actual renderer follow-game method without opening
native windows. Chat to Items failed before the one-condition correction and
passed afterward. Alt-Tab and minimized-game cases are covered separately.
Native screen confirmation remains pending; automated tests are not live UI proof.

This is an APWorld/client-only update. Keep the r3 native patch, running game,
existing room/server, and saves. Replace the client package with the client closed,
then reconnect to the same room. Do not reinstall/reset the mod for this fix.
