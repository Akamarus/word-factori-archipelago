from dataclasses import dataclass

from Options import Choice, PerGameCommonOptions, Range


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


class CampaignLayoutOption(Choice):
    """Choose whether levels retain native pages or shuffle within a balanced campaign."""
    display_name = "Campaign Layout"
    option_fixed_pages = 0
    option_shuffled_pages = 1
    default = 1


@dataclass
class WordFactoriOptions(PerGameCommonOptions):
    goal: Goal
    campaign_count: CampaignCount
    custom_level_set: CustomLevelSet
    campaign_layout: CampaignLayoutOption
