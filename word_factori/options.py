from dataclasses import dataclass

from Options import Choice, DefaultOnToggle, OptionList, PerGameCommonOptions, Range, Toggle, StartInventoryPool


class Goal(Choice):
    """Choose how the client reports victory."""
    display_name = "Goal"
    option_campaign_count = 0
    option_final_factory = 1
    default = 0


class CampaignCount(Range):
    """Campaign checks required when Goal is Campaign Count."""
    display_name = "Campaign Count"
    range_start = 20
    range_end = 30
    default = 25


class CustomLevelSet(Choice):
    """Choose the curated custom levels assembled into this seed."""
    display_name = "Custom Level Set"
    option_core_campaign = 0
    option_discovery_labs = 1
    default = 1

class RecipeChecks(DefaultOnToggle):
    """Add checks for discovering validated letter recipes."""
    display_name = "Recipe Checks"


class TypeAWordChecks(Toggle):
    """Add checks for filling seed-selected Type-a-Word orders."""
    display_name = "Type-a-Word Checks"
    default = 0


class ProgressiveMachines(Toggle):
    """Machine upgrades allow 1, 2, 3, 4, then unlimited placed machines per family."""
    display_name = "Progressive Machines"
    default = 0


class TypeAWordCount(Range):
    """Number of Type-a-Word orders to add."""
    display_name = "Type-a-Word Count"
    range_start = 1
    range_end = 20
    default = 5


class TypeAWordWords(OptionList):
    """Targets of 2–12 supported letters/symbols. Quote numeric and punctuation entries in YAML."""
    display_name = "Type-a-Word Words"
    default = ()

    @staticmethod
    def _validate_shape(value: object) -> None:
        if not isinstance(value, (list, tuple)):
            raise ValueError(
                "type_a_word_words must be a YAML list, for example: [JACK, ISLAND]"
            )

    def __init__(self, value):
        self._validate_shape(value)
        super().__init__(value)

    @classmethod
    def from_any(cls, value):
        cls._validate_shape(value)
        return super().from_any(value)


@dataclass
class WordFactoriOptions(PerGameCommonOptions):
    start_inventory_from_pool: StartInventoryPool
    goal: Goal
    campaign_count: CampaignCount
    custom_level_set: CustomLevelSet
    recipe_checks: RecipeChecks
    type_a_word_checks: TypeAWordChecks
    type_a_word_count: TypeAWordCount
    type_a_word_words: TypeAWordWords
    progressive_machines: ProgressiveMachines
