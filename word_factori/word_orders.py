from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from importlib.resources import files
import itertools
import json
import random
import re
import string

from .recipe_graph import MACHINE_CAPABILITIES


FIRST_WORD_ORDER_CODE = 975303000
ALPHABET_LOGIC_VERSION = 1
_MAX_WORD_ORDERS = 20
_MAX_WORD_LIST_ENTRIES = 200
_CAPABILITIES = tuple(sorted(set(MACHINE_CAPABILITIES.values())))
_CAPABILITY_SET = frozenset(_CAPABILITIES)
_LOWERCASE_SHA256 = re.compile(r"[0-9a-f]{64}").fullmatch


def _load_alphabet_catalog() -> tuple[dict[str, tuple[frozenset[str], ...]], str]:
    raw = files(__package__).joinpath("data/alphabet_requirements.json").read_text(
        encoding="utf-8"
    )
    payload = json.loads(raw)
    if not isinstance(payload, dict) or set(payload) != {"version", "digest", "alphabet"}:
        raise ValueError("alphabet catalog must contain only version, digest and alphabet")
    version, digest, alphabet = (
        payload["version"], payload["digest"], payload["alphabet"]
    )
    if type(version) is not int or version != ALPHABET_LOGIC_VERSION:
        raise ValueError("alphabet catalog version is invalid")
    if not isinstance(digest, str) or _LOWERCASE_SHA256(digest) is None:
        raise ValueError("alphabet catalog digest is invalid")
    if not isinstance(alphabet, dict) or set(alphabet) != set(string.ascii_uppercase):
        raise ValueError("alphabet catalog must contain exactly A through Z")

    validated: dict[str, tuple[frozenset[str], ...]] = {}
    for letter in string.ascii_uppercase:
        requirements = alphabet[letter]
        if not isinstance(requirements, list) or not requirements:
            raise ValueError(f"alphabet catalog requirements for {letter} are invalid")
        options: list[frozenset[str]] = []
        for option in requirements:
            if (
                not isinstance(option, list)
                or not all(isinstance(value, str) for value in option)
                or option != sorted(option)
            ):
                raise ValueError(f"alphabet catalog route for {letter} is invalid")
            frozen = frozenset(option)
            if len(frozen) != len(option) or not frozen <= _CAPABILITY_SET:
                raise ValueError(f"alphabet catalog route for {letter} has invalid capabilities")
            options.append(frozen)
        if len(set(options)) != len(options) or any(
            left < right for left in options for right in options
        ):
            raise ValueError(f"alphabet catalog routes for {letter} are not minimal")
        if options != sorted(options, key=lambda option: (len(option), tuple(sorted(option)))):
            raise ValueError(f"alphabet catalog routes for {letter} are not canonical")
        validated[letter] = tuple(options)

    canonical = json.dumps(
        alphabet, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if hashlib.sha256(canonical).hexdigest() != digest:
        raise ValueError("alphabet catalog digest does not match its contents")
    return validated, digest


_ALPHABET_REQUIREMENTS, ALPHABET_LOGIC_DIGEST = _load_alphabet_catalog()
_CAPABILITY_SUBSETS = tuple(
    frozenset(combination)
    for count in range(len(_CAPABILITIES) + 1)
    for combination in itertools.combinations(_CAPABILITIES, count)
)


def _normalize_word(word: object) -> str:
    if not isinstance(word, str):
        raise ValueError("word-list entries must be strings")
    stripped = word.strip()
    if not 2 <= len(stripped) <= 12:
        raise ValueError("words must contain between 2 and 12 ASCII letters")
    if not all("A" <= character <= "Z" or "a" <= character <= "z" for character in stripped):
        raise ValueError("words must contain only ASCII letters")
    return stripped.upper()


def normalize_word_list(words: object) -> tuple[str, ...]:
    if isinstance(words, (str, bytes, bytearray)) or not isinstance(words, Sequence):
        raise ValueError("word list must be a sequence")
    if len(words) > _MAX_WORD_LIST_ENTRIES:
        raise ValueError("word list cannot contain more than 200 entries")
    return tuple(sorted({_normalize_word(word) for word in words}))


@lru_cache(maxsize=4096)
def _requirements_for_normalized_word(word: str) -> tuple[frozenset[str], ...]:
    solutions = [
        owned
        for owned in _CAPABILITY_SUBSETS
        if all(
            any(route <= owned for route in _ALPHABET_REQUIREMENTS[letter])
            for letter in set(word)
        )
    ]
    return tuple(
        owned for owned in solutions
        if not any(other < owned for other in solutions)
    )


def word_requirement_options(word: str) -> tuple[frozenset[str], ...]:
    return _requirements_for_normalized_word(_normalize_word(word))


def missing_machine_options(
    word: str, owned: Iterable[str]
) -> tuple[frozenset[str], ...]:
    if isinstance(owned, (str, bytes, bytearray)):
        raise ValueError("owned capabilities must be an iterable of capability names")
    try:
        owned_set = frozenset(owned)
    except TypeError as error:
        raise ValueError("owned capabilities must be an iterable of capability names") from error
    if not all(isinstance(value, str) for value in owned_set) or not owned_set <= _CAPABILITY_SET:
        raise ValueError("owned capabilities contain an unknown machine family")

    candidates: list[frozenset[str]] = []
    for route in word_requirement_options(word):
        missing = route - owned_set
        if missing not in candidates:
            candidates.append(missing)
    return tuple(
        option for option in candidates
        if not any(other < option for other in candidates)
    )


@dataclass(frozen=True)
class WordOrder:
    number: int
    word: str

    def __post_init__(self) -> None:
        if type(self.number) is not int or not 1 <= self.number <= _MAX_WORD_ORDERS:
            raise ValueError("word order number must be between 1 and 20")
        if _normalize_word(self.word) != self.word:
            raise ValueError("word order target must be normalized")

    @property
    def code(self) -> int:
        return FIRST_WORD_ORDER_CODE + self.number - 1

    @property
    def name(self) -> str:
        return f"Word Order {self.number:02d}"

    @property
    def requirements(self) -> tuple[frozenset[str], ...]:
        return word_requirement_options(self.word)


WORD_ORDER_NAME_TO_ID = {
    f"Word Order {number:02d}": FIRST_WORD_ORDER_CODE + number - 1
    for number in range(1, _MAX_WORD_ORDERS + 1)
}


def choose_word_orders(
    words: object, count: int, rng: random.Random
) -> tuple[WordOrder, ...]:
    if type(count) is not int or not 1 <= count <= _MAX_WORD_ORDERS:
        raise ValueError("word order count must be between 1 and 20")
    normalized = normalize_word_list(words)
    if len(normalized) < count:
        raise ValueError("word list has fewer distinct valid words than the requested count")
    selected = rng.sample(normalized, count)
    return tuple(WordOrder(index + 1, word) for index, word in enumerate(selected))


def _validated_orders(orders: Sequence[WordOrder]) -> tuple[WordOrder, ...]:
    if isinstance(orders, (str, bytes, bytearray)) or not isinstance(orders, Sequence):
        raise ValueError("word orders must be a sequence")
    if len(orders) > _MAX_WORD_ORDERS:
        raise ValueError("word orders cannot contain more than 20 entries")
    result = tuple(orders)
    if not all(isinstance(order, WordOrder) for order in result):
        raise ValueError("word orders contain an invalid entry")
    if any(order.number != index for index, order in enumerate(result, start=1)):
        raise ValueError("word order numbers must be contiguous and ordered")
    if len({order.word for order in result}) != len(result):
        raise ValueError("word order targets must be unique")
    return result


def orders_slot_data(orders: Sequence[WordOrder]) -> dict:
    validated = _validated_orders(orders)
    if not validated:
        return {"type_a_word_checks": False}
    return {
        "type_a_word_checks": True,
        "word_orders": [
            {"id": order.code, "name": order.name, "word": order.word}
            for order in validated
        ],
        "alphabet_logic_version": ALPHABET_LOGIC_VERSION,
        "alphabet_logic_digest": ALPHABET_LOGIC_DIGEST,
    }


def orders_from_slot_data(slot_data: Mapping) -> tuple[WordOrder, ...]:
    if not isinstance(slot_data, Mapping):
        raise ValueError("slot data must be an object")
    enabled = slot_data.get("type_a_word_checks", False)
    if type(enabled) is not bool:
        raise ValueError("type_a_word_checks must be a boolean")
    enabled_fields = {
        "word_orders", "alphabet_logic_version", "alphabet_logic_digest"
    }
    if not enabled:
        if any(field in slot_data for field in enabled_fields):
            raise ValueError("disabled Type-a-Word checks cannot include order metadata")
        return ()
    if not enabled_fields <= set(slot_data):
        raise ValueError("enabled Type-a-Word checks require complete order metadata")
    if (
        type(slot_data["alphabet_logic_version"]) is not int
        or slot_data["alphabet_logic_version"] != ALPHABET_LOGIC_VERSION
    ):
        raise ValueError("alphabet logic version does not match")
    if slot_data["alphabet_logic_digest"] != ALPHABET_LOGIC_DIGEST:
        raise ValueError("alphabet logic digest does not match")

    raw_orders = slot_data["word_orders"]
    if not isinstance(raw_orders, list) or not 1 <= len(raw_orders) <= _MAX_WORD_ORDERS:
        raise ValueError("enabled word_orders must contain between 1 and 20 entries")
    orders: list[WordOrder] = []
    for number, item in enumerate(raw_orders, start=1):
        if not isinstance(item, dict) or set(item) != {"id", "name", "word"}:
            raise ValueError("word order metadata has an invalid shape")
        expected_code = FIRST_WORD_ORDER_CODE + number - 1
        expected_name = f"Word Order {number:02d}"
        if type(item["id"]) is not int or item["id"] != expected_code:
            raise ValueError("word order IDs must be contiguous and ordered")
        if not isinstance(item["name"], str) or item["name"] != expected_name:
            raise ValueError("word order names must be contiguous and ordered")
        normalized = _normalize_word(item["word"])
        if normalized != item["word"]:
            raise ValueError("word order targets must be normalized")
        orders.append(WordOrder(number, normalized))
    return _validated_orders(orders)


def checks_contract_digest(slot_data: Mapping) -> str:
    orders = orders_from_slot_data(slot_data)
    recipe_checks = slot_data.get("recipe_checks", False)
    if type(recipe_checks) is not bool:
        raise ValueError("recipe_checks must be a boolean")

    canonical: dict[str, object] = {
        "recipe_checks": recipe_checks,
        "type_a_word_checks": bool(orders),
    }
    if recipe_checks:
        from .recipe_checks import RECIPE_CATALOG_DIGEST

        if slot_data.get("recipe_catalog_digest") != RECIPE_CATALOG_DIGEST:
            raise ValueError("recipe catalog digest does not match")
        canonical["recipe_catalog_digest"] = RECIPE_CATALOG_DIGEST
    elif "recipe_catalog_digest" in slot_data:
        raise ValueError("disabled recipe checks cannot include a recipe catalog digest")
    if orders:
        canonical.update(orders_slot_data(orders))

    encoded = json.dumps(
        canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
