from __future__ import annotations

from typing import Protocol


class CapabilityRecord(Protocol):
    stable_key: str
    kind: str
    required_route: frozenset[str]
    requirement_options: tuple[frozenset[str], ...]


FULL = frozenset({
    "Bender Access", "Rotation Access", "Reflection Access",
    "Merger2 Access", "Merger3 Access", "Merger4 Access",
})
CHALLENGE_REQUIREMENTS = {
    "challenge-cat-compact": (
        frozenset({"Bender Access", "Rotation Access", "Reflection Access", "Merger2 Access"}),
    ),
    "challenge-book-low-cycles": (
        frozenset({"Bender Access", "Rotation Access", "Reflection Access", "Merger2 Access", "Merger3 Access"}),
    ),
    "challenge-phone-no-waste": (FULL,),
}


def requirements_for_record(record: CapabilityRecord) -> tuple[frozenset[str], ...]:
    if record.kind == "discovery":
        return (record.required_route,)
    if record.kind == "challenge":
        try:
            return CHALLENGE_REQUIREMENTS[record.stable_key]
        except KeyError as error:
            raise ValueError(f"unknown challenge requirements: {record.stable_key}") from error
    return record.requirement_options


def unavoidable_nonbootstrap_machines(record: CapabilityRecord) -> frozenset[str]:
    routes = requirements_for_record(record)
    if not routes:
        raise ValueError(f"campaign requirements are empty for {record.stable_key}")
    unavoidable = set(routes[0])
    for route in routes[1:]:
        unavoidable.intersection_update(route)
    unavoidable.discard("Bender Access")
    return frozenset(unavoidable)
