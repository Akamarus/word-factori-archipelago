from dataclasses import dataclass

from Options import Choice, DefaultOnToggle, PerGameCommonOptions, Range


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


@dataclass
class WordFactoriOptions(PerGameCommonOptions):
    goal: Goal
    campaign_count: CampaignCount
    custom_level_set: CustomLevelSet
    recipe_checks: RecipeChecks
