# Word Factori Hybrid Multiworld Setup

Run the release's `install.ps1`, restart Archipelago and Word Factori, and select **word factori archipelago** with an empty game save slot. The bundled campaign has 30 main factories followed by ten Discovery Labs.

Generate a new 1.1.0 room, launch **Word Factori Client**, and connect to it. Received machine items and Progressive World Access copies update the mod's supported `levels.json`; return to save select or restart Word Factori after new unlocks.

The client reads completed level indices but never writes the Word Factori save. It binds each room to one empty save slot and refuses checks if existing progress is present or the active slot changes. It also refuses checks and mod regeneration if the connected room and installed campaign identities differ.
