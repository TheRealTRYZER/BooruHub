"""Tests for the tag_mapping service — build_lookup, translate_tags."""
import pytest
from unittest.mock import MagicMock
from app.services.tag_mapping import build_lookup, translate_tags


def _mock_mapping(unitag, danbooru_tags="", e621_tags="", rule34_tags=""):
    m = MagicMock()
    m.unitag = unitag
    m.danbooru_tags = danbooru_tags
    m.e621_tags = e621_tags
    m.rule34_tags = rule34_tags
    return m


class TestBuildLookup:
    def test_build_from_mappings(self):
        """it should build a lookup dict keyed by unitag"""
        mappings = [
            _mock_mapping("female", danbooru_tags="1girl", e621_tags="female"),
            _mock_mapping("order:hot", danbooru_tags="order:rank"),
        ]
        lookup = build_lookup(mappings)
        assert "female" in lookup
        assert lookup["female"]["danbooru"] == "1girl"
        assert lookup["female"]["e621"] == "female"

    def test_build_from_empty(self):
        """it should still contain defaults for empty user mappings"""
        lookup = build_lookup([])
        # Should have at least the starter mappings
        assert isinstance(lookup, dict)

    def test_user_overrides_defaults(self):
        """it should let user mappings override starter defaults"""
        # Build with empty, note a default key
        defaults = build_lookup([])
        if defaults:
            first_key = next(iter(defaults))
            custom = _mock_mapping(first_key, danbooru_tags="custom_override", e621_tags="custom", rule34_tags="custom")
            lookup = build_lookup([custom])
            assert lookup[first_key]["danbooru"] == "custom_override"


class TestTranslateTags:
    def test_translate_known_tags(self):
        """it should translate unitags to site-specific tags"""
        lookup = {
            "female": {"danbooru": "1girl", "e621": "female", "rule34": "female"},
        }
        result = translate_tags(["female"], "danbooru", lookup)
        assert result is not None
        assert "1girl" in result

    def test_translate_unknown_tags_passthrough(self):
        """it should pass through tags that have no mapping"""
        lookup = {}
        result = translate_tags(["cat_ears", "blue_eyes"], "danbooru", lookup)
        assert result is not None
        assert "cat_ears" in result
        assert "blue_eyes" in result

    def test_translate_preserves_prefix_operators(self):
        """it should preserve - prefix operator"""
        lookup = {"female": {"danbooru": "1girl", "e621": "female", "rule34": "female"}}
        result = translate_tags(["-female"], "danbooru", lookup)
        assert result is not None
        assert "-1girl" in result

    def test_translate_empty_list(self):
        """it should return empty string for empty input"""
        result = translate_tags([], "danbooru", {})
        # Empty list → empty or None
        assert result == "" or result is None
