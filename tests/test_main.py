from unittest.mock import patch, MagicMock
from src.main import parse_args, run, load_keywords, SCHEDULE_TO_SOURCES


def test_parse_args_defaults():
    a = parse_args(["--window", "6h"])
    assert a.window == "6h"
    assert a.sources == "hourly"


def test_parse_args_manual_all():
    a = parse_args(["--window", "24h", "--sources", "all"])
    assert a.sources == "all"


def test_schedule_to_sources_map():
    assert set(SCHEDULE_TO_SOURCES["hourly"]) == {
        "remotive", "remoteok", "weworkremotely",
        "linkedin", "indeed", "glassdoor",
    }
    assert SCHEDULE_TO_SOURCES["6h"] == ["adzuna"]
    assert SCHEDULE_TO_SOURCES["12h"] == ["jsearch"]
    assert set(SCHEDULE_TO_SOURCES["all"]) == {
        "remotive", "remoteok", "weworkremotely", "adzuna", "jsearch",
        "linkedin", "indeed", "glassdoor",
    }


def test_load_keywords_returns_flat_list():
    kws = load_keywords()
    assert isinstance(kws, list)
    assert "GoHighLevel" in kws
    assert "HubSpot" in kws
    assert len(kws) >= 30
