"""Tests for the blacklist service."""
import pytest
from app.services.blacklist import parse_blacklist, filter_posts, matches_rule


class TestParseBlacklist:
    def test_parse_simple_tags(self):
        """it should parse simple tag rules"""
        rules = parse_blacklist("gore\nscat")
        assert len(rules) == 2
        assert "gore" in rules[0].include_tags
        assert "scat" in rules[1].include_tags

    def test_parse_exclude_operator(self):
        """it should parse exclude (-) operator"""
        rules = parse_blacklist("gore -safe")
        assert len(rules) == 1
        assert "gore" in rules[0].include_tags
        assert "safe" in rules[0].exclude_tags

    def test_parse_any_operator(self):
        """it should parse any (~) operator"""
        rules = parse_blacklist("~gore ~blood")
        assert len(rules) == 1
        assert "gore" in rules[0].any_tags
        assert "blood" in rules[0].any_tags

    def test_parse_multi_tag_rule(self):
        """it should parse multi-tag rules (all must match)"""
        rules = parse_blacklist("gore blood")
        assert len(rules) == 1
        assert rules[0].include_tags == {"gore", "blood"}

    def test_parse_empty_rules(self):
        """it should return empty list for empty input"""
        assert parse_blacklist("") == []
        assert parse_blacklist("  ") == []

    def test_parse_comments_ignored(self):
        """it should ignore comment lines"""
        rules = parse_blacklist("# this is a comment\ngore")
        assert len(rules) == 1

    def test_parse_rating_filter(self):
        """it should handle rating: prefixed tags"""
        rules = parse_blacklist("rating:explicit")
        assert len(rules) == 1
        assert rules[0].rating_filter == "explicit"

    def test_parse_score_filter(self):
        """it should handle score: prefixed tags"""
        rules = parse_blacklist("score:<10")
        assert len(rules) == 1
        assert rules[0].score_filter == "<10"


class TestMatchesRule:
    def test_match_include_tag(self):
        """it should match when all include tags are present"""
        rules = parse_blacklist("gore blood")
        post = {"tags": ["gore", "blood", "other"], "rating": "e", "score": 0}
        assert matches_rule(post, rules[0])

    def test_no_match_partial_include(self):
        """it should not match when only some include tags are present"""
        rules = parse_blacklist("gore blood")
        post = {"tags": ["gore", "other"], "rating": "e", "score": 0}
        assert not matches_rule(post, rules[0])

    def test_exclude_prevents_match(self):
        """it should not match when exclude tag is present"""
        rules = parse_blacklist("gore -safe")
        post = {"tags": ["gore", "safe"], "rating": "e", "score": 0}
        assert not matches_rule(post, rules[0])

    def test_rating_match(self):
        """it should match by rating"""
        rules = parse_blacklist("rating:explicit")
        post = {"tags": [], "rating": "e", "score": 0}
        assert matches_rule(post, rules[0])

    def test_rating_no_match(self):
        """it should not match different rating"""
        rules = parse_blacklist("rating:explicit")
        post = {"tags": [], "rating": "g", "score": 0}
        assert not matches_rule(post, rules[0])


class TestFilterPosts:
    def test_filter_matching_posts(self):
        """it should remove posts matching blacklist rules"""
        posts = [
            {"id": "1", "tags": ["cat", "cute"], "rating": "g", "score": 0},
            {"id": "2", "tags": ["gore", "blood"], "rating": "e", "score": 0},
            {"id": "3", "tags": ["dog", "happy"], "rating": "g", "score": 0},
        ]
        rules = parse_blacklist("gore")
        filtered = filter_posts(posts, rules)
        assert len(filtered) == 2
        assert all(p["id"] != "2" for p in filtered)

    def test_filter_multi_tag_rule(self):
        """it should only filter posts matching ALL tags in a rule"""
        posts = [
            {"id": "1", "tags": ["gore"], "rating": "e", "score": 0},
            {"id": "2", "tags": ["gore", "blood"], "rating": "e", "score": 0},
            {"id": "3", "tags": ["blood"], "rating": "e", "score": 0},
        ]
        rules = parse_blacklist("gore blood")
        filtered = filter_posts(posts, rules)
        assert len(filtered) == 2
        assert all(p["id"] != "2" for p in filtered)

    def test_filter_no_rules(self):
        """it should return all posts when no rules exist"""
        posts = [{"id": "1", "tags": ["anything"], "rating": "g", "score": 0}]
        assert filter_posts(posts, []) == posts

    def test_filter_empty_posts(self):
        """it should handle empty post list"""
        rules = parse_blacklist("gore")
        assert filter_posts([], rules) == []
