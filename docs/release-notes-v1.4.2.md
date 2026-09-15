# Word Factori Archipelago 1.4.2 — Linux Setup Fixes

This tester prerelease fixes the Linux installation failures reported with 1.4.1.

- Accepts both native Archipelago user-world directories: `worlds` and `custom_worlds`.
- Resolves an explicitly selected Archipelago directory shortcut, displays its real destination, and records that destination consistently.
- Fixes the client rejecting a valid `worlds` installation receipt after setup.
- Gives a more specific error for an invalid Archipelago destination.
- Keeps checks against redirected APWorld files, hardlinks, and destinations inside the game or Proton prefix.

## Install or update

Download **word-factori-archipelago-1.4.2.zip** below, not GitHub's source-code archives. The same player ZIP supports Windows and Linux.

Close Word Factori and Archipelago, and extract the new ZIP into a separate folder so any manually edited installer files are not reused.

On Linux, open a terminal in that folder and run:

```bash
bash "Install Word Factori Archipelago.sh"
```

Select the existing user-world directory loaded by your native Archipelago installation (`worlds` or `custom_worlds`). Directory shortcuts are supported; confirm the real destination shown by setup. Restart Archipelago afterward so it loads the updated APWorld/client, connect to your room, then start the game through Steam Proton.

On Windows, run **Install Word Factori Archipelago.cmd** as before.

Do not delete your saves or original-game backup. Matching 1.4.0 and 1.4.1 rooms retain the same campaign contract and bound save; new rooms still require an empty mod save. Pre-1.4.0 rooms remain unsupported.

See the [Linux guide](https://github.com/Akamarus/word-factori-archipelago/blob/v1.4.2/docs/linux-proton.md) for setup, verification, restore, uninstall, and recovery.

## Verification and limitations

Regression coverage includes installer-to-client receipt validation, both directory names, directory shortcuts, install/update/restore/uninstall, safety checks, and client checks/items/reconnect/victory using `worlds`. Windows and Ubuntu automated verification passed for the fix.

Real Linux/Proton gameplay remains unverified. The in-game AP Mail overlay remains Windows-only; Linux uses the regular Archipelago client for items and chat.

The reported 9–10-second generation time is a separate issue and is **not fixed in this release**.
