"""Tests for E621 and Rule34 booru providers."""
import pytest
from app.services.booru.e621 import E621
from app.services.booru.rule34 import Rule34


class TestE621Normalization:
    def setup_method(self):
        self.provider = E621()

    def test_normalize_post_with_full_data(self):
        """it should normalize a complete e621 post correctly"""
        raw = {
            "id": 12345,
            "file": {"url": "https://static1.e621.net/data/123.png", "width": 1920, "height": 1080, "ext": "png", "md5": "abc123"},
            "preview": {"url": "/data/preview/123.jpg"},
            "sample": {"url": "/data/sample/123.jpg"},
            "tags": {
                "general": ["cat", "sitting"],
                "species": ["feline"],
                "character": ["garfield"],
            },
            "score": {"total": 42},
            "rating": "s",
            "created_at": "2024-01-01T00:00:00Z",
        }
        post = self.provider.normalize_post(raw)
        assert post is not None
        assert post["id"] == "12345"
        assert post["source_site"] == "e621"
        assert post["rating"] == "g"  # 's' maps to 'g' for e621
        assert post["score"] == 42
        assert "cat" in post["tags"]
        assert "feline" in post["tags"]
        assert "garfield" in post["tags"]
        assert post["width"] == 1920
        assert post["preview_url"].startswith("https://e621.net/")

    def test_normalize_post_no_file_url(self):
        """it should return None when file URL is missing"""
        raw = {"id": 1, "file": {}, "tags": {}}
        assert self.provider.normalize_post(raw) is None

    def test_normalize_post_plain_score(self):
        """it should handle plain integer score (not nested dict)"""
        raw = {
            "id": 99,
            "file": {"url": "https://example.com/file.jpg", "width": 100, "height": 100, "ext": "jpg"},
            "tags": {"general": ["test"]},
            "score": 77,
            "rating": "e",
        }
        post = self.provider.normalize_post(raw)
        assert post["score"] == 77
        assert post["rating"] == "e"

    def test_prepare_tags_returns_tuple(self):
        """it should return (tags, []) since e621 has no tag limit"""
        api_tags, extra = self.provider.prepare_tags("cat dog")
        assert api_tags == "cat dog"
        assert extra == []


class TestRule34Normalization:
    def setup_method(self):
        self.provider = Rule34()

    def test_normalize_post_with_full_data(self):
        """it should normalize a complete Rule34 post correctly"""
        raw = {
            "id": 9999,
            "file_url": "https://api-cdn.rule34.xxx/images/123/image.png",
            "preview_url": "https://api-cdn.rule34.xxx/thumbnails/123/thumbnail.jpg",
            "sample_url": "https://api-cdn.rule34.xxx/samples/123/sample.jpg",
            "tags": "cat ears tail",
            "rating": "explicit",
            "score": 55,
            "width": 800,
            "height": 600,
            "hash": "deadbeef",
            "created_at": "2024-01-01",
        }
        post = self.provider.normalize_post(raw)
        assert post is not None
        assert post["id"] == "9999"
        assert post["source_site"] == "rule34"
        assert post["rating"] == "e"
        assert post["tags"] == ["cat", "ears", "tail"]
        assert post["file_ext"] == "png"
        assert post["md5"] == "deadbeef"

    def test_normalize_post_no_file_url(self):
        """it should return None when file URL is missing"""
        raw = {"id": 1}
        assert self.provider.normalize_post(raw) is None

    def test_normalize_post_safe_rating(self):
        """it should map safe/general to 'g'"""
        raw = {
            "id": 1,
            "file_url": "https://example.com/file.jpg",
            "tags": "test",
            "rating": "safe",
        }
        post = self.provider.normalize_post(raw)
        assert post["rating"] == "g"

    def test_calculate_page_offset(self):
        """it should calculate pid as offset-based pagination"""
        assert self.provider.calculate_page(1, 40) == 0
        assert self.provider.calculate_page(2, 40) == 40
        assert self.provider.calculate_page(3, 50) == 100

    def test_prepare_tags_returns_tuple(self):
        """it should return (tags, []) since Rule34 doesn't split tags"""
        api_tags, extra = self.provider.prepare_tags("cat dog")
        assert api_tags == "cat dog"
        assert extra == []
