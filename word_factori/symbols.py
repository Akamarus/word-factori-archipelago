"""Verified target characters and native output identities (not arbitrary Unicode)."""
import string

SPECIAL_CHARACTERS = "()#%$@+=&0123456789🔑🚪~"
TARGET_CHARACTERS = string.ascii_uppercase + SPECIAL_CHARACTERS
TARGET_SET = frozenset(TARGET_CHARACTERS)
# Native Letter.toString() retains the rotation; goal matching uses aliasedChar().
TARGET_TOKENS = {character: ("62" if character == "9" else character)
                 for character in TARGET_CHARACTERS}
