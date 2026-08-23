# Word Factori Hybrid Multiworld Setup

Extract the release, close Word Factori and Archipelago, and double-click **Install Word Factori Archipelago.cmd**. Restart both programs, then select **word factori archipelago** with an empty game save slot. The bundled campaign has 30 main factories followed by ten Discovery Labs.

For an update, run `powershell -ExecutionPolicy Bypass -File .\install.ps1 -Force`. To remove only this integration's APWorld and mod folder, run the same command with `-Uninstall`.

Generate a new 1.1.0 room, launch **Word Factori Client**, and connect to it. Received machine items and Progressive World Access copies update the mod's supported `levels.json`; return to save select or restart Word Factori after new unlocks.

The client reads completed level indices but never writes the Word Factori save. It binds each room to one empty save slot and refuses checks if existing progress is present or the active slot changes. It also refuses checks and mod regeneration if the connected room and installed campaign identities differ.

Received items appear as blue popups on the left side of Word Factori. Click **AP MAIL** or press **F8** for the item ledger. The display works in windowed and borderless modes; use the regular Word Factori Client in exclusive fullscreen. If it does not appear, use `/wf_overlay status` and `/wf_overlay restart`. The overlay is optional, so item delivery and check reporting continue if its renderer stops.
