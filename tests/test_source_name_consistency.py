"""T3 regression: every source's NAME must match what main.py and sheets.py expect."""
from src.main import SOURCE_NAMES, SCHEDULE_TO_SOURCES
from src.sources.adzuna import AdzunaSource
from src.sources.glassdoor import GlassdoorSource
from src.sources.indeed import IndeedSource
from src.sources.jsearch import JSearchSource
from src.sources.linkedin import LinkedInSource
from src.sources.remoteok import RemoteOKSource
from src.sources.remotive import RemotiveSource
from src.sources.weworkremotely import WeWorkRemotelySource


SOURCE_CLASSES = {
    "remotive": RemotiveSource,
    "remoteok": RemoteOKSource,
    "weworkremotely": WeWorkRemotelySource,
    "adzuna": AdzunaSource,
    "jsearch": JSearchSource,
    "linkedin": LinkedInSource,
    "indeed": IndeedSource,
    "glassdoor": GlassdoorSource,
}


def test_source_names_match_class_attribute():
    for key, cls in SOURCE_CLASSES.items():
        assert cls.NAME == SOURCE_NAMES[key], (
            f"{cls.__name__}.NAME ({cls.NAME!r}) != SOURCE_NAMES[{key!r}] ({SOURCE_NAMES[key]!r})"
        )


def test_all_source_schedule_keys_have_canonical_name():
    for src_key in SCHEDULE_TO_SOURCES["all"]:
        assert src_key in SOURCE_NAMES, f"{src_key} missing from SOURCE_NAMES map"


def test_api_source_names_set_matches_tier1():
    # main.py has a hardcoded set for routing to API Sources tab
    expected_api = {"Remotive", "RemoteOK", "WeWorkRemotely", "Adzuna", "JSearch"}
    actual_api = {SOURCE_NAMES[k] for k in ("remotive", "remoteok", "weworkremotely", "adzuna", "jsearch")}
    assert actual_api == expected_api
