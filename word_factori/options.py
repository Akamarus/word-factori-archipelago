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


@dataclass
class WordFactoriOptions(PerGameCommonOptions):
    goal: Goal
    campaign_count: CampaignCount
