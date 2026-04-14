"""Unit tests for audiogram_generator.core.captioning module."""
import pytest

from audiogram_generator.core.captioning import (
    build_caption_text,
    format_srt_time,
    generate_srt_content,
    normalize_hashtags,
)


class TestNormalizeHashtags:
    def test_single_source_basic(self):
        result = normalize_hashtags(["python", "devops"])
        assert result == ["python", "devops"]

    def test_strips_leading_hash(self):
        result = normalize_hashtags(["#python", "#devops"])
        assert result == ["python", "devops"]

    def test_lowercases(self):
        result = normalize_hashtags(["Python", "DEVOPS"])
        assert result == ["python", "devops"]

    def test_removes_inner_spaces(self):
        result = normalize_hashtags(["machine learning"])
        assert result == ["machinelearning"]

    def test_deduplicates_across_sources(self):
        result = normalize_hashtags(["python", "ai"], ["python", "devops"])
        assert result == ["python", "ai", "devops"]

    def test_none_sources_are_ignored(self):
        result = normalize_hashtags(None, ["python"], None)
        assert result == ["python"]

    def test_none_items_inside_source_are_ignored(self):
        result = normalize_hashtags([None, "python", None])
        assert result == ["python"]

    def test_empty_sources_return_empty(self):
        result = normalize_hashtags([], [])
        assert result == []

    def test_no_arguments_returns_empty(self):
        result = normalize_hashtags()
        assert result == []

    def test_removes_invalid_chars(self):
        # Dashes, dots, etc. should be stripped
        result = normalize_hashtags(["hello-world"])
        assert result == ["helloworld"]

    def test_preserves_order(self):
        result = normalize_hashtags(["c", "a", "b"])
        assert result == ["c", "a", "b"]

    def test_multiple_sources_merged_in_order(self):
        result = normalize_hashtags(["first"], ["second"], ["third"])
        assert result == ["first", "second", "third"]


class TestBuildCaptionText:
    def test_basic_structure(self):
        caption = build_caption_text(
            episode_number=42,
            episode_title="My Episode",
            episode_link="https://example.com/ep42",
            soundbite_title="Great Soundbite",
            transcript_text="Some transcript.",
        )
        assert "42: My Episode" in caption
        assert "Great Soundbite" in caption
        assert "Some transcript." in caption
        assert "https://example.com/ep42" in caption

    def test_hashtags_from_podcast_keywords(self):
        caption = build_caption_text(
            episode_number=1,
            episode_title="Title",
            episode_link="https://example.com/ep1",
            soundbite_title="Bite",
            transcript_text="Text.",
            podcast_keywords="python,coding",
        )
        assert "#python" in caption
        assert "#coding" in caption

    def test_hashtags_from_episode_keywords(self):
        caption = build_caption_text(
            episode_number=1,
            episode_title="Title",
            episode_link="https://example.com",
            soundbite_title="Bite",
            transcript_text="Text.",
            episode_keywords="ai, ml",
        )
        assert "#ai" in caption
        assert "#ml" in caption

    def test_hashtags_from_config(self):
        caption = build_caption_text(
            episode_number=1,
            episode_title="Title",
            episode_link="https://example.com",
            soundbite_title="Bite",
            transcript_text="Text.",
            config_hashtags=["devops", "tech"],
        )
        assert "#devops" in caption
        assert "#tech" in caption

    def test_fallback_to_podcast_hashtag_when_no_keywords(self):
        caption = build_caption_text(
            episode_number=1,
            episode_title="Title",
            episode_link="https://example.com",
            soundbite_title="Bite",
            transcript_text="Text.",
        )
        assert "#podcast" in caption

    def test_custom_episode_prefix(self):
        caption = build_caption_text(
            episode_number=5,
            episode_title="Title",
            episode_link="https://example.com",
            soundbite_title="Bite",
            transcript_text="Text.",
            episode_prefix="Episodio",
        )
        assert "Episodio 5:" in caption

    def test_custom_listen_prefix(self):
        caption = build_caption_text(
            episode_number=1,
            episode_title="Title",
            episode_link="https://example.com",
            soundbite_title="Bite",
            transcript_text="Text.",
            listen_full_prefix="Ascolta l'episodio completo",
        )
        assert "Ascolta l'episodio completo:" in caption


class TestFormatSrtTime:
    def test_zero(self):
        assert format_srt_time(0.0) == "00:00:00,000"

    def test_seconds_only(self):
        assert format_srt_time(5.5) == "00:00:05,500"

    def test_minutes_and_seconds(self):
        assert format_srt_time(65.25) == "00:01:05,250"

    def test_hours_minutes_seconds(self):
        assert format_srt_time(3661.0) == "01:01:01,000"


class TestGenerateSrtContent:
    def test_single_chunk(self):
        chunks = [{"start": 0.0, "end": 5.0, "text": "Hello World"}]
        result = generate_srt_content(chunks)
        assert "1" in result
        assert "00:00:00,000 --> 00:00:05,000" in result
        assert "Hello World" in result

    def test_multiple_chunks_numbered(self):
        chunks = [
            {"start": 0.0, "end": 3.0, "text": "First"},
            {"start": 3.0, "end": 6.0, "text": "Second"},
        ]
        result = generate_srt_content(chunks)
        assert "1\n" in result
        assert "2\n" in result
        assert "First" in result
        assert "Second" in result

    def test_empty_chunks(self):
        result = generate_srt_content([])
        assert result == ""
