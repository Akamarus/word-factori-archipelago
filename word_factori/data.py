from __future__ import annotations

from dataclasses import dataclass

from .campaign import CampaignManifest, campaign_digest, campaign_for_level_set

GAME = "Word Factori"
BASE_ID = 975_300_000


@dataclass(frozen=True)
class LocationData:
    stable_key: str
    index: int
    name: str
    target: str
    region: str
    kind: str = "word"
    world_tier: int = 0
    required_route: frozenset[str] = frozenset()
    requirement_options: tuple[frozenset[str], ...] = ()
    module_limits: tuple[tuple[str, int], ...] = ()

    @property
    def code(self) -> int:
        return BASE_ID + 1000 + self.index


DEFAULT_LEVEL_SET = "discovery_labs"
_CAMPAIGN = campaign_for_level_set(DEFAULT_LEVEL_SET)
CAMPAIGN_ID = _CAMPAIGN.campaign_id
CAMPAIGN_VERSION = _CAMPAIGN.version
CAMPAIGN_DIGEST = campaign_digest(_CAMPAIGN)
def locations_for_manifest(manifest: CampaignManifest) -> tuple[LocationData, ...]:
    return tuple(LocationData(
        stable_key=record.stable_key,
        index=record.index,
        name=record.name,
        target=record.target,
        region=record.region,
        kind=record.kind,
        world_tier=record.world_tier,
        required_route=record.required_route,
        requirement_options=record.requirement_options,
        module_limits=record.module_limits,
    )
        for record in manifest.levels
    )


def locations_for_level_set(level_set: str) -> tuple[LocationData, ...]:
    return locations_for_manifest(campaign_for_level_set(level_set))


LOCATIONS = locations_for_manifest(_CAMPAIGN)
LOCATION_NAME_TO_ID = {location.name: location.code for location in LOCATIONS}

MACHINE_ITEMS = (
    "Bender Access", "Rotation Access", "Reflection Access", "Merger2 Access", "Merger3 Access", "Merger4 Access"
)
PERMIT_ITEMS = (
    "Short Pack Permit", "Intermediate Pack Permit", "Advanced Pack Permit", "Challenge Board Permit", "Final Pack Permit"
)
LEGACY_ITEM_NAMES = MACHINE_ITEMS + ("Progressive Word Length",) + PERMIT_ITEMS + (
    "Recipe Hint", "Factory Tip", "Sticker Parcel",
)
STICKER_NAMES = (
    "I Sticker", "C Sticker", "CAT Sticker", "OWL Sticker", "DRAGON Sticker", "PITCHFORK Sticker",
)
NEW_ITEM_NAMES = ("Progressive World Access",) + STICKER_NAMES
ITEM_NAMES = LEGACY_ITEM_NAMES + NEW_ITEM_NAMES
ITEM_NAME_TO_ID = {name: BASE_ID + index for index, name in enumerate(ITEM_NAMES, start=1)}
PROGRESSION_ITEMS = MACHINE_ITEMS[1:] + ("Progressive World Access",) * 5
STICKER_ITEMS = tuple(sticker for sticker in STICKER_NAMES for _ in range(5))
ITEM_POOL = PROGRESSION_ITEMS + STICKER_ITEMS

REGION_REQUIREMENTS = {
    "Starter Workshop": 0,
    "Short Word Bench": 1,
    "Main Factory": 2,
    "Advanced Factory": 3,
    "Challenge Board": 4,
    "Final Contract": 5,
}
