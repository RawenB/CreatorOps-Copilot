import pytest

from creatorops.tools.compliance import check_post_compliance


def rules(*args, **kwargs):
    result = check_post_compliance(*args, with_sources=False, **kwargs)
    return result["verdict"], [p["rule"] for p in result["problems"]]


def test_clear_disclosure_at_the_start_is_compliant():
    assert rules("#ad New collection is out", "instagram", True, True) == ("compliant", [])


def test_organic_post_needs_nothing():
    assert rules("Morning run", "tiktok", False) == ("compliant", [])


@pytest.mark.parametrize(
    "caption, expected",
    [
        ("Love this serum", "missing_disclosure"),
        ("Love this serum #spon", "vague_disclosure"),
        (
            "My whole routine from cleanser to serum to sunscreen, honestly the best #ad",
            "disclosure_not_at_start",
        ),
        ("Glow #skincare #beauty #ad #glow #love", "disclosure_in_hashtags"),
    ],
)
def test_disclosure_problems(caption, expected):
    verdict, problems = rules(caption, "instagram", True, True)
    assert verdict == "non_compliant" and expected in problems


def test_platform_rules():
    assert "label_off_tiktok" in rules("#ad hi", "tiktok", True, False)[1]
    assert "prohibited_tobacco" in rules("#ad vape", "tiktok", True, True, "tobacco")[1]
    assert "no_age_restriction" in rules("#ad gin", "instagram", True, True, "alcohol", False)[1]
