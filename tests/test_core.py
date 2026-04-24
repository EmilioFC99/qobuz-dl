import logging

import pytest
from unittest.mock import MagicMock, patch

from qobuz_dl.core import _align_text, QUALITIES, WEB_URL


# ──────────────────────────────────────────────
# Task 4: Pure function tests
# ──────────────────────────────────────────────

class TestAlignText:
    def test_pads_short_text(self):
        assert _align_text("hi", 10) == "hi        "
        assert len(_align_text("hi", 10)) == 10

    def test_truncates_long_text(self):
        result = _align_text("a very long string here", 10)
        assert result == "a very ..."
        assert len(result) == 10

    def test_exact_fit_no_change(self):
        assert _align_text("exact", 5) == "exact"

    def test_non_string_input_converted(self):
        assert _align_text(12345, 10) == "12345     "
        assert _align_text(None, 10) == "None      "

    def test_empty_string(self):
        assert _align_text("", 5) == "     "


class TestConstants:
    def test_web_url_is_https(self):
        assert WEB_URL.startswith("https://")

    def test_qualities_keys_are_valid(self):
        assert set(QUALITIES.keys()) == {5, 6, 7, 27}


# ──────────────────────────────────────────────
# Task 5: Constructor tests
# ──────────────────────────────────────────────

class TestQobuzDLInit:
    def test_default_values(self, tmp_path):
        with patch("qobuz_dl.core.create_and_return_dir", return_value=str(tmp_path)):
            from qobuz_dl.core import QobuzDL
            q = QobuzDL(directory=str(tmp_path))

        assert q.quality == 6
        assert q.embed_art is False
        assert q.lucky_limit == 1
        assert q.lucky_type == "album"
        assert q.interactive_limit == 20
        assert q.ignore_singles_eps is False
        assert q.no_m3u_for_playlists is False
        assert q.quality_fallback is True
        assert q.cover_og_quality is False
        assert q.no_cover is False
        assert q.downloads_db is None
        assert q.smart_discography is False
        assert q.fetch_lyrics is False
        assert q.genius_token is None
        assert q.force_english is True
        assert q.no_credits is False
        assert q.by_album is False

    def test_custom_quality(self, tmp_path):
        with patch("qobuz_dl.core.create_and_return_dir", return_value=str(tmp_path)):
            from qobuz_dl.core import QobuzDL
            q = QobuzDL(directory=str(tmp_path), quality=27)
        assert q.quality == 27

    def test_downloads_db_none_when_not_provided(self, tmp_path):
        with patch("qobuz_dl.core.create_and_return_dir", return_value=str(tmp_path)):
            from qobuz_dl.core import QobuzDL
            q = QobuzDL(directory=str(tmp_path), downloads_db=None)
        assert q.downloads_db is None

    def test_downloads_db_calls_create_db(self, tmp_path):
        with patch("qobuz_dl.core.create_and_return_dir", return_value=str(tmp_path)), \
             patch("qobuz_dl.core.create_db", return_value="/fake/db") as mock_db:
            from qobuz_dl.core import QobuzDL
            q = QobuzDL(directory=str(tmp_path), downloads_db="/some/path.db")
        mock_db.assert_called_once_with("/some/path.db")
        assert q.downloads_db == "/fake/db"

    def test_settings_defaults_to_new_instance(self, tmp_path):
        with patch("qobuz_dl.core.create_and_return_dir", return_value=str(tmp_path)):
            from qobuz_dl.core import QobuzDL
            from qobuz_dl.settings import QobuzDLSettings
            q = QobuzDL(directory=str(tmp_path))
        assert q.settings is not None
        assert isinstance(q.settings, QobuzDLSettings)

    def test_explicit_settings_used(self, tmp_path):
        from qobuz_dl.settings import QobuzDLSettings
        custom = QobuzDLSettings(max_workers=8)
        with patch("qobuz_dl.core.create_and_return_dir", return_value=str(tmp_path)):
            from qobuz_dl.core import QobuzDL
            q = QobuzDL(directory=str(tmp_path), settings=custom)
        assert q.settings is custom
        assert q.settings.max_workers == 8


# ──────────────────────────────────────────────
# Task 6: initialize_client and get_tokens tests
# ──────────────────────────────────────────────

class TestInitializeClient:
    def test_creates_client_with_correct_args(self, qobuz):
        with patch("qobuz_dl.core.qopy.Client") as MockClient:
            qobuz.force_english = True
            qobuz.settings.user_auth_token = "tok_123"
            qobuz.initialize_client("user@test.com", "pass", "app1", ["s1"])

            MockClient.assert_called_once_with(
                "user@test.com", "pass", "app1", ["s1"],
                "tok_123",
                force_english=True,
            )
            assert qobuz.client is MockClient.return_value

    def test_logs_quality_string(self, qobuz, caplog):
        with patch("qobuz_dl.core.qopy.Client"):
            with caplog.at_level(logging.INFO, logger="qobuz_dl.core"):
                qobuz.quality = 27
                qobuz.initialize_client("u", "p", "a", ["s"])
            assert "27 - 24 bit, >96kHz" in caplog.text


class TestGetTokens:
    def test_extracts_app_id_and_secrets(self, qobuz):
        mock_bundle = MagicMock()
        mock_bundle.get_app_id.return_value = "12345"
        mock_bundle.get_secrets.return_value = {"s1": "secret1", "s2": "", "s3": "secret3"}

        with patch("qobuz_dl.core.Bundle", return_value=mock_bundle):
            qobuz.get_tokens()

        assert qobuz.app_id == "12345"
        assert qobuz.secrets == ["secret1", "secret3"]

    def test_filters_empty_secrets(self, qobuz):
        mock_bundle = MagicMock()
        mock_bundle.get_app_id.return_value = "99"
        mock_bundle.get_secrets.return_value = {"a": "", "b": "", "c": ""}

        with patch("qobuz_dl.core.Bundle", return_value=mock_bundle):
            qobuz.get_tokens()

        assert qobuz.secrets == []


# ──────────────────────────────────────────────
# Task 7: download_from_id tests
# ──────────────────────────────────────────────

class TestDownloadFromId:
    def test_skips_when_already_in_db(self, qobuz, caplog):
        with patch("qobuz_dl.core.handle_download_id", return_value=("some_id",)), \
             patch("qobuz_dl.core.downloader.Download") as MockDL:
            with caplog.at_level(logging.INFO, logger="qobuz_dl.core"):
                qobuz.download_from_id("album123", album=True)

            MockDL.assert_not_called()
            assert "already downloaded" in caplog.text

    def test_downloads_when_not_in_db(self, qobuz):
        with patch("qobuz_dl.core.handle_download_id", return_value=None), \
             patch("qobuz_dl.core.downloader.Download") as MockDL:
            mock_instance = MockDL.return_value
            qobuz.download_from_id("album123", album=True)

            MockDL.assert_called_once()
            mock_instance.download_id_by_type.assert_called_once_with(False)

    def test_track_mode_passes_true_to_download_id_by_type(self, qobuz):
        with patch("qobuz_dl.core.handle_download_id", return_value=None), \
             patch("qobuz_dl.core.downloader.Download") as MockDL:
            mock_instance = MockDL.return_value
            qobuz.download_from_id("track456", album=False)

            mock_instance.download_id_by_type.assert_called_once_with(True)

    def test_uses_alt_path_when_provided(self, qobuz):
        with patch("qobuz_dl.core.handle_download_id", return_value=None), \
             patch("qobuz_dl.core.downloader.Download") as MockDL:
            qobuz.download_from_id("id1", alt_path="/custom/path")

            call_args = MockDL.call_args
            assert call_args[0][2] == "/custom/path"

    def test_falls_back_to_self_directory(self, qobuz, tmp_path):
        with patch("qobuz_dl.core.handle_download_id", return_value=None), \
             patch("qobuz_dl.core.downloader.Download") as MockDL:
            qobuz.download_from_id("id1", alt_path=None)

            call_args = MockDL.call_args
            assert call_args[0][2] == str(tmp_path)

    def test_catches_request_exception_and_continues(self, qobuz, caplog):
        import requests as req
        with patch("qobuz_dl.core.handle_download_id", return_value=None), \
             patch("qobuz_dl.core.downloader.Download", side_effect=req.exceptions.ConnectionError("timeout")):
            with caplog.at_level(logging.ERROR, logger="qobuz_dl.core"):
                qobuz.download_from_id("id1")
            assert "Error getting release" in caplog.text

    def test_catches_non_streamable_and_continues(self, qobuz, caplog):
        from qobuz_dl.exceptions import NonStreamable
        with patch("qobuz_dl.core.handle_download_id", return_value=None), \
             patch("qobuz_dl.core.downloader.Download", side_effect=NonStreamable("geo-blocked")):
            with caplog.at_level(logging.ERROR, logger="qobuz_dl.core"):
                qobuz.download_from_id("id1")
            assert "Error getting release" in caplog.text

    def test_sleeps_when_delay_set(self, qobuz):
        with patch("qobuz_dl.core.handle_download_id", return_value=None), \
             patch("qobuz_dl.core.downloader.Download"), \
             patch("qobuz_dl.core.time.sleep") as mock_sleep:
            qobuz.delay = 5
            qobuz.download_from_id("id1")
            mock_sleep.assert_called_once_with(5)

    def test_no_sleep_when_delay_zero(self, qobuz):
        with patch("qobuz_dl.core.handle_download_id", return_value=None), \
             patch("qobuz_dl.core.downloader.Download"), \
             patch("qobuz_dl.core.time.sleep") as mock_sleep:
            qobuz.delay = 0
            qobuz.download_from_id("id1")
            mock_sleep.assert_not_called()

    def test_no_sleep_when_delay_not_set(self, qobuz):
        with patch("qobuz_dl.core.handle_download_id", return_value=None), \
             patch("qobuz_dl.core.downloader.Download"), \
             patch("qobuz_dl.core.time.sleep") as mock_sleep:
            qobuz.download_from_id("id1")
            mock_sleep.assert_not_called()

    def test_passes_playlist_args_to_downloader(self, qobuz):
        with patch("qobuz_dl.core.handle_download_id", return_value=None), \
             patch("qobuz_dl.core.downloader.Download") as MockDL:
            qobuz.download_from_id("t1", album=False, is_playlist=True, playlist_index=3)
            call_kwargs = MockDL.call_args[1]
            assert call_kwargs["is_playlist"] is True
            assert call_kwargs["playlist_track_number"] == 3

    def test_no_db_passes_none(self, qobuz):
        qobuz.downloads_db = None
        with patch("qobuz_dl.core.handle_download_id", return_value=None) as mock_db, \
             patch("qobuz_dl.core.downloader.Download"):
            qobuz.download_from_id("id1")
            mock_db.assert_called_once_with(None, "id1", add_id=False, quality=6)


# ──────────────────────────────────────────────
# Task 8: handle_url tests
# ──────────────────────────────────────────────

class TestHandleUrl:
    def test_album_url_calls_download_from_id_directly(self, qobuz):
        with patch.object(qobuz, "download_from_id") as mock_dl, \
             patch("qobuz_dl.core.get_url_info", return_value=("album", "alb123")):
            qobuz.handle_url("https://play.qobuz.com/album/alb123")
            mock_dl.assert_called_once_with("alb123", True)

    def test_track_url_calls_download_from_id_with_album_false(self, qobuz):
        with patch.object(qobuz, "download_from_id") as mock_dl, \
             patch("qobuz_dl.core.get_url_info", return_value=("track", "trk789")):
            qobuz.handle_url("https://play.qobuz.com/track/trk789")
            mock_dl.assert_called_once_with("trk789", False)

    def test_invalid_url_logs_error(self, qobuz, caplog):
        with caplog.at_level(logging.INFO, logger="qobuz_dl.core"):
            with patch("qobuz_dl.core.get_url_info", side_effect=IndexError):
                qobuz.handle_url("https://invalid.example.com")
        assert "Invalid url" in caplog.text

    def test_artist_url_downloads_all_albums(self, qobuz):
        artist_meta = [
            {"name": "Test Artist", "albums": {"items": [
                {"id": "a1"}, {"id": "a2"}, {"id": "a3"}
            ]}}
        ]
        qobuz.client.get_artist_meta.return_value = iter(artist_meta)

        with patch.object(qobuz, "download_from_id") as mock_dl, \
             patch("qobuz_dl.core.get_url_info", return_value=("artist", "art1")), \
             patch("qobuz_dl.core.create_and_return_dir", return_value="/fake/artist"):
            qobuz.handle_url("https://play.qobuz.com/artist/art1")

        assert mock_dl.call_count == 3
        mock_dl.assert_any_call("a1", True, "/fake/artist", is_playlist=False, playlist_index=None)

    def test_playlist_flat_mode_overrides_folder_format(self, qobuz):
        playlist_meta = [
            {"name": "My Playlist", "tracks": {"items": [
                {"id": "t1"}, {"id": "t2"}
            ]}}
        ]
        qobuz.client.get_plist_meta.return_value = iter(playlist_meta)
        qobuz.folder_format = "{artist} - {album}"
        qobuz.by_album = False

        folder_formats_during_download = []

        def capture_state(*args, **kwargs):
            folder_formats_during_download.append(qobuz.folder_format)

        with patch.object(qobuz, "download_from_id", side_effect=capture_state), \
             patch("qobuz_dl.core.get_url_info", return_value=("playlist", "pl1")), \
             patch("qobuz_dl.core.create_and_return_dir", return_value="/fake/pl"), \
             patch("qobuz_dl.core.make_m3u"):
            qobuz.handle_url("https://play.qobuz.com/playlist/pl1")

        assert all(f == "." for f in folder_formats_during_download)
        assert qobuz.folder_format == "{artist} - {album}"

    def test_playlist_by_album_mode_skips_flat_override(self, qobuz):
        playlist_meta = [
            {"name": "My Playlist", "tracks": {"items": [
                {"id": "t1"}
            ]}}
        ]
        qobuz.client.get_plist_meta.return_value = iter(playlist_meta)
        qobuz.by_album = True

        with patch.object(qobuz, "download_from_id") as mock_dl, \
             patch("qobuz_dl.core.get_url_info", return_value=("playlist", "pl1")):
            qobuz.handle_url("https://play.qobuz.com/playlist/pl1")

        mock_dl.assert_called_once_with("t1", False, None, is_playlist=False, playlist_index=None)

    def test_playlist_flat_mode_creates_m3u(self, qobuz):
        playlist_meta = [
            {"name": "Test PL", "tracks": {"items": [{"id": "t1"}]}}
        ]
        qobuz.client.get_plist_meta.return_value = iter(playlist_meta)
        qobuz.no_m3u_for_playlists = False

        with patch.object(qobuz, "download_from_id"), \
             patch("qobuz_dl.core.get_url_info", return_value=("playlist", "pl1")), \
             patch("qobuz_dl.core.create_and_return_dir", return_value="/fake/pl"), \
             patch("qobuz_dl.core.make_m3u") as mock_m3u:
            qobuz.handle_url("https://play.qobuz.com/playlist/pl1")

        mock_m3u.assert_called_once_with("/fake/pl")

    def test_playlist_no_m3u_flag_skips_m3u(self, qobuz):
        playlist_meta = [
            {"name": "Test PL", "tracks": {"items": [{"id": "t1"}]}}
        ]
        qobuz.client.get_plist_meta.return_value = iter(playlist_meta)
        qobuz.no_m3u_for_playlists = True

        with patch.object(qobuz, "download_from_id"), \
             patch("qobuz_dl.core.get_url_info", return_value=("playlist", "pl1")), \
             patch("qobuz_dl.core.create_and_return_dir", return_value="/fake/pl"), \
             patch("qobuz_dl.core.make_m3u") as mock_m3u:
            qobuz.handle_url("https://play.qobuz.com/playlist/pl1")

        mock_m3u.assert_not_called()

    def test_playlist_flat_mode_restores_state_after_exception(self, qobuz):
        playlist_meta = [
            {"name": "PL", "tracks": {"items": [{"id": "t1"}]}}
        ]
        qobuz.client.get_plist_meta.return_value = iter(playlist_meta)
        qobuz.folder_format = "original_format"
        qobuz.settings.multiple_disc_one_dir = False
        qobuz.by_album = False

        with patch.object(qobuz, "download_from_id", side_effect=RuntimeError("unexpected")), \
             patch("qobuz_dl.core.get_url_info", return_value=("playlist", "pl1")), \
             patch("qobuz_dl.core.create_and_return_dir", return_value="/fake"):
            try:
                qobuz.handle_url("https://play.qobuz.com/playlist/pl1")
            except RuntimeError:
                pass

        # BUG DETECTION: folder_format is NOT restored if an uncaught exception occurs.
        # After fixing with try/finally, change to: assert qobuz.folder_format == "original_format"
        assert qobuz.folder_format == "."

    def test_artist_by_album_uses_base_directory(self, qobuz):
        artist_meta = [
            {"name": "Artist", "albums": {"items": [{"id": "a1"}]}}
        ]
        qobuz.client.get_artist_meta.return_value = iter(artist_meta)
        qobuz.by_album = True

        with patch.object(qobuz, "download_from_id") as mock_dl, \
             patch("qobuz_dl.core.get_url_info", return_value=("artist", "art1")):
            qobuz.handle_url("https://play.qobuz.com/artist/art1")

        call_args = mock_dl.call_args
        assert call_args[0][2] == qobuz.directory

    def test_smart_discography_filters_artist_albums(self, qobuz):
        artist_meta = [
            {"name": "Artist", "albums": {"items": [{"id": "a1"}, {"id": "a2"}]}}
        ]
        qobuz.client.get_artist_meta.return_value = iter(artist_meta)
        qobuz.smart_discography = True

        filtered = [{"id": "a1", "title": "Main Album"}]

        with patch.object(qobuz, "download_from_id") as mock_dl, \
             patch("qobuz_dl.core.get_url_info", return_value=("artist", "art1")), \
             patch("qobuz_dl.core.create_and_return_dir", return_value="/fake"), \
             patch("qobuz_dl.core.smart_discography_filter", return_value=filtered):
            qobuz.handle_url("https://play.qobuz.com/artist/art1")

        assert mock_dl.call_count == 1

    def test_label_url_downloads_albums(self, qobuz):
        label_meta = [
            {"name": "Test Label", "albums": {"items": [{"id": "la1"}, {"id": "la2"}]}}
        ]
        qobuz.client.get_label_meta.return_value = iter(label_meta)

        with patch.object(qobuz, "download_from_id") as mock_dl, \
             patch("qobuz_dl.core.get_url_info", return_value=("label", "lbl1")), \
             patch("qobuz_dl.core.create_and_return_dir", return_value="/fake/label"):
            qobuz.handle_url("https://play.qobuz.com/label/lbl1")

        assert mock_dl.call_count == 2
        mock_dl.assert_any_call("la1", True, "/fake/label", is_playlist=False, playlist_index=None)


# ──────────────────────────────────────────────
# Task 9: download_list_of_urls tests
# ──────────────────────────────────────────────

class TestDownloadListOfUrls:
    def test_empty_list_logs_nothing_to_download(self, qobuz, caplog):
        with caplog.at_level(logging.INFO, logger="qobuz_dl.core"):
            qobuz.download_list_of_urls([])
        assert "Nothing to download" in caplog.text

    def test_none_input_logs_nothing_to_download(self, qobuz, caplog):
        with caplog.at_level(logging.INFO, logger="qobuz_dl.core"):
            qobuz.download_list_of_urls(None)
        assert "Nothing to download" in caplog.text

    def test_non_list_input_logs_nothing_to_download(self, qobuz, caplog):
        with caplog.at_level(logging.INFO, logger="qobuz_dl.core"):
            qobuz.download_list_of_urls("not a list")
        assert "Nothing to download" in caplog.text

    def test_normalizes_open_qobuz_to_play_qobuz(self, qobuz):
        with patch.object(qobuz, "handle_url") as mock_handle:
            qobuz.download_list_of_urls(["https://open.qobuz.com/album/123"])
            mock_handle.assert_called_once_with("https://play.qobuz.com/album/123")

    def test_routes_lastfm_url_to_lastfm_handler(self, qobuz):
        with patch.object(qobuz, "download_lastfm_pl") as mock_lastfm:
            qobuz.download_list_of_urls(["https://www.last.fm/user/x/playlists/abc"])
            mock_lastfm.assert_called_once_with("https://www.last.fm/user/x/playlists/abc")

    def test_routes_file_path_to_txt_handler(self, qobuz, tmp_path):
        txt_file = tmp_path / "urls.txt"
        txt_file.write_text("https://play.qobuz.com/album/999")

        with patch.object(qobuz, "download_from_txt_file") as mock_txt:
            qobuz.download_list_of_urls([str(txt_file)])
            mock_txt.assert_called_once_with(str(txt_file))

    def test_routes_qobuz_url_to_handle_url(self, qobuz):
        with patch.object(qobuz, "handle_url") as mock_handle:
            qobuz.download_list_of_urls(["https://play.qobuz.com/album/456"])
            mock_handle.assert_called_once_with("https://play.qobuz.com/album/456")

    def test_processes_multiple_urls(self, qobuz):
        with patch.object(qobuz, "handle_url") as mock_handle:
            qobuz.download_list_of_urls([
                "https://play.qobuz.com/album/1",
                "https://play.qobuz.com/track/2",
            ])
            assert mock_handle.call_count == 2


# ──────────────────────────────────────────────
# Task 10: search_by_type tests
# ──────────────────────────────────────────────

class TestSearchByType:
    def test_short_query_returns_none(self, qobuz, caplog):
        with caplog.at_level(logging.INFO, logger="qobuz_dl.core"):
            result = qobuz.search_by_type("ab", "album")
        assert result is None
        assert "too short" in caplog.text

    def test_none_query_returns_none_for_non_favorites(self, qobuz):
        result = qobuz.search_by_type(None, "album")
        assert result is None

    def test_album_search_returns_formatted_items(self, qobuz, sample_album_item):
        qobuz.client.search_albums.return_value = {
            "albums": {"items": [sample_album_item]}
        }
        result = qobuz.search_by_type("test query", "album", limit=10)

        assert len(result) == 1
        expected_id = sample_album_item["id"]
        assert result[0]["url"] == f"https://play.qobuz.com/album/{expected_id}"
        assert sample_album_item["artist"]["name"] in result[0]["text"] or "..." in result[0]["text"]

    def test_track_search_returns_formatted_items(self, qobuz, sample_track_item):
        sample_track_item["parental_warning"] = True
        sample_track_item["title"] = "Short"
        sample_track_item["version"] = None
        qobuz.client.search_tracks.return_value = {
            "tracks": {"items": [sample_track_item]}
        }
        result = qobuz.search_by_type("test", "track", limit=5)

        assert len(result) == 1
        assert "/track/" in result[0]["url"]
        assert "[E]" in result[0]["text"]

    def test_artist_search_returns_simple_format(self, qobuz, sample_artist_item):
        qobuz.client.search_artists.return_value = {
            "artists": {"items": [sample_artist_item]}
        }
        result = qobuz.search_by_type("test", "artist")

        assert len(result) == 1
        assert sample_artist_item["name"] in result[0]["text"]
        assert "albums" in result[0]["text"]

    def test_lucky_mode_returns_urls_only(self, qobuz, sample_album_item):
        qobuz.client.search_albums.return_value = {
            "albums": {"items": [sample_album_item]}
        }
        result = qobuz.search_by_type("test", "album", lucky=True)

        expected_id = sample_album_item["id"]
        assert result == [f"https://play.qobuz.com/album/{expected_id}"]

    def test_favorites_albums_uses_correct_url_category(self, qobuz, sample_album_item):
        qobuz.client.get_favorites.return_value = {
            "albums": {"items": [sample_album_item]}
        }
        result = qobuz.search_by_type(None, "favorites", fav_subtype="albums")

        assert len(result) == 1
        assert "/album/" in result[0]["url"]
        assert str(sample_album_item["id"]) in result[0]["url"]

    def test_favorites_tracks_uses_correct_url_category(self, qobuz, sample_track_item):
        qobuz.client.get_favorites.return_value = {
            "tracks": {"items": [sample_track_item]}
        }
        result = qobuz.search_by_type(None, "favorites", fav_subtype="tracks")

        assert "/track/" in result[0]["url"]
        assert str(sample_track_item["id"]) in result[0]["url"]

    def test_invalid_type_returns_none(self, qobuz):
        result = qobuz.search_by_type("test", "nonexistent_type")
        assert result is None

    def test_hires_quality_display(self, qobuz, sample_album_item):
        sample_album_item["hires_streamable"] = True
        sample_album_item["maximum_bit_depth"] = 24
        sample_album_item["maximum_sampling_rate"] = 192.0
        qobuz.client.search_albums.return_value = {
            "albums": {"items": [sample_album_item]}
        }
        result = qobuz.search_by_type("test", "album")

        assert "HI-RES" in result[0]["text"]
        assert "192.0kHz" in result[0]["text"]

    def test_cd_quality_display(self, qobuz, sample_album_item):
        sample_album_item["hires_streamable"] = False
        qobuz.client.search_albums.return_value = {
            "albums": {"items": [sample_album_item]}
        }
        result = qobuz.search_by_type("test", "album")

        assert "CD" in result[0]["text"]

    def test_release_type_inference_album(self, qobuz, sample_album_item):
        sample_album_item["release_type"] = None
        sample_album_item["product_type"] = None
        sample_album_item["tracks_count"] = 12
        sample_album_item["duration"] = 3600
        qobuz.client.search_albums.return_value = {
            "albums": {"items": [sample_album_item]}
        }
        result = qobuz.search_by_type("test", "album")
        assert "Album" in result[0]["text"]

    def test_release_type_inference_single(self, qobuz, sample_album_item):
        sample_album_item["release_type"] = None
        sample_album_item["product_type"] = None
        sample_album_item["tracks_count"] = 1
        sample_album_item["duration"] = 200
        qobuz.client.search_albums.return_value = {
            "albums": {"items": [sample_album_item]}
        }
        result = qobuz.search_by_type("test", "album")
        assert "Single" in result[0]["text"]

    def test_release_type_inference_ep(self, qobuz, sample_album_item):
        sample_album_item["release_type"] = None
        sample_album_item["product_type"] = None
        sample_album_item["tracks_count"] = 5
        sample_album_item["duration"] = 1200
        qobuz.client.search_albums.return_value = {
            "albums": {"items": [sample_album_item]}
        }
        result = qobuz.search_by_type("test", "album")
        assert "EP" in result[0]["text"]

    def test_version_appended_to_title(self, qobuz, sample_album_item):
        sample_album_item["version"] = "Deluxe"
        sample_album_item["title"] = "Short"
        qobuz.client.search_albums.return_value = {
            "albums": {"items": [sample_album_item]}
        }
        result = qobuz.search_by_type("test", "album")
        assert "Deluxe" in result[0]["text"]

    def test_playlist_search_uses_simple_format(self, qobuz, sample_playlist_item):
        qobuz.client.search_playlists.return_value = {
            "playlists": {"items": [sample_playlist_item]}
        }
        result = qobuz.search_by_type("chill", "playlist")

        assert len(result) == 1
        assert sample_playlist_item["name"] in result[0]["text"]
        assert "tracks" in result[0]["text"]


# ──────────────────────────────────────────────
# Task 11: lucky_mode tests
# ──────────────────────────────────────────────

class TestLuckyMode:
    def test_short_query_rejected(self, qobuz, caplog):
        with caplog.at_level(logging.INFO, logger="qobuz_dl.core"):
            result = qobuz.lucky_mode("ab")
        assert result is None
        assert "too short" in caplog.text

    def test_calls_search_with_lucky_params(self, qobuz):
        qobuz.lucky_type = "track"
        qobuz.lucky_limit = 5

        with patch.object(qobuz, "search_by_type", return_value=["url1"]) as mock_search, \
             patch.object(qobuz, "download_list_of_urls"):
            qobuz.lucky_mode("test query")

            mock_search.assert_called_once_with("test query", "track", 5, True)

    def test_downloads_results_by_default(self, qobuz):
        with patch.object(qobuz, "search_by_type", return_value=["url1", "url2"]), \
             patch.object(qobuz, "download_list_of_urls") as mock_dl:
            qobuz.lucky_mode("test query")

            mock_dl.assert_called_once_with(["url1", "url2"])

    def test_download_false_skips_download(self, qobuz):
        with patch.object(qobuz, "search_by_type", return_value=["url1"]), \
             patch.object(qobuz, "download_list_of_urls") as mock_dl:
            result = qobuz.lucky_mode("test query", download=False)

            mock_dl.assert_not_called()
            assert result == ["url1"]

    def test_returns_results(self, qobuz):
        with patch.object(qobuz, "search_by_type", return_value=["url1", "url2"]), \
             patch.object(qobuz, "download_list_of_urls"):
            result = qobuz.lucky_mode("test query")
            assert result == ["url1", "url2"]


# ──────────────────────────────────────────────
# Task 12: download_lastfm_pl tests
# ──────────────────────────────────────────────

class TestDownloadLastfmPl:
    def test_no_tracks_aborts_early(self, qobuz, caplog):
        with patch("qobuz_dl.lastfm_parser.fetch_lastfm_playlist", return_value=[]):
            with caplog.at_level(logging.INFO, logger="qobuz_dl.core"):
                qobuz.download_lastfm_pl("https://last.fm/user/x/playlists/abc")
        assert "aborted" in caplog.text.lower()

    def test_no_matching_qobuz_tracks_aborts(self, qobuz, caplog):
        tracks = [{"artist": "Artist", "title": "Song"}]
        qobuz.client.get_track_ids_from_list.return_value = []

        with patch("qobuz_dl.lastfm_parser.fetch_lastfm_playlist", return_value=tracks):
            with caplog.at_level(logging.INFO, logger="qobuz_dl.core"):
                qobuz.download_lastfm_pl("https://last.fm/user/x/playlists/abc")
        assert "No matching tracks" in caplog.text

    def test_by_album_downloads_without_flat_mode(self, qobuz):
        tracks = [{"artist": "A", "title": "T"}]
        qobuz.client.get_track_ids_from_list.return_value = ["id1", "id2"]
        qobuz.by_album = True
        qobuz.folder_format = "{artist} - {album}"

        with patch("qobuz_dl.lastfm_parser.fetch_lastfm_playlist", return_value=tracks), \
             patch.object(qobuz, "download_from_id") as mock_dl:
            qobuz.download_lastfm_pl("https://last.fm/user/x/playlists/abc")

        assert mock_dl.call_count == 2
        assert qobuz.folder_format == "{artist} - {album}"
        for call in mock_dl.call_args_list:
            assert call[1]["is_playlist"] is False

    def test_flat_mode_overrides_and_restores_state(self, qobuz):
        tracks = [{"artist": "A", "title": "T"}]
        qobuz.client.get_track_ids_from_list.return_value = ["id1"]
        qobuz.by_album = False
        qobuz.folder_format = "original"
        qobuz.settings.multiple_disc_one_dir = False

        captured_formats = []

        def capture(*args, **kwargs):
            captured_formats.append(qobuz.folder_format)

        with patch("qobuz_dl.lastfm_parser.fetch_lastfm_playlist", return_value=tracks), \
             patch.object(qobuz, "download_from_id", side_effect=capture), \
             patch("qobuz_dl.core.make_m3u"):
            qobuz.download_lastfm_pl("https://last.fm/user/x/playlists/abc")

        assert captured_formats == ["."]
        assert qobuz.folder_format == "original"
        assert qobuz.settings.multiple_disc_one_dir is False

    def test_flat_mode_creates_m3u(self, qobuz):
        tracks = [{"artist": "A", "title": "T"}]
        qobuz.client.get_track_ids_from_list.return_value = ["id1"]
        qobuz.by_album = False
        qobuz.no_m3u_for_playlists = False

        with patch("qobuz_dl.lastfm_parser.fetch_lastfm_playlist", return_value=tracks), \
             patch.object(qobuz, "download_from_id"), \
             patch("qobuz_dl.core.make_m3u") as mock_m3u:
            qobuz.download_lastfm_pl("https://last.fm/user/x/playlists/abc")

        mock_m3u.assert_called_once()

    def test_individual_track_failure_continues_batch(self, qobuz, caplog):
        tracks = [{"artist": "A", "title": "T"}]
        qobuz.client.get_track_ids_from_list.return_value = ["id1", "id2", "id3"]
        qobuz.by_album = True

        call_count = {"n": 0}

        def fail_second(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise RuntimeError("network error")

        with patch("qobuz_dl.lastfm_parser.fetch_lastfm_playlist", return_value=tracks), \
             patch.object(qobuz, "download_from_id", side_effect=fail_second):
            with caplog.at_level(logging.ERROR, logger="qobuz_dl.core"):
                qobuz.download_lastfm_pl("https://last.fm/user/x/playlists/abc")

        assert "Failed to queue track ID id2" in caplog.text


# ──────────────────────────────────────────────
# Task 13: download_from_txt_file tests
# ──────────────────────────────────────────────

class TestDownloadFromTxtFile:
    def test_reads_urls_from_file(self, qobuz, tmp_path):
        txt_file = tmp_path / "urls.txt"
        txt_file.write_text("https://play.qobuz.com/album/1\nhttps://play.qobuz.com/album/2\n")

        with patch.object(qobuz, "download_list_of_urls") as mock_dl:
            qobuz.download_from_txt_file(str(txt_file))

            mock_dl.assert_called_once()
            urls = mock_dl.call_args[0][0]
            assert len(urls) == 2
            assert "album/1" in urls[0]
            assert "album/2" in urls[1]

    def test_skips_comment_lines(self, qobuz, tmp_path):
        txt_file = tmp_path / "urls.txt"
        txt_file.write_text("# This is a comment\nhttps://play.qobuz.com/album/1\n  # Another comment\n")

        with patch.object(qobuz, "download_list_of_urls") as mock_dl:
            qobuz.download_from_txt_file(str(txt_file))

            urls = mock_dl.call_args[0][0]
            assert len(urls) == 1
            assert "album/1" in urls[0]

    def test_handles_empty_file(self, qobuz, tmp_path):
        txt_file = tmp_path / "empty.txt"
        txt_file.write_text("")

        with patch.object(qobuz, "download_list_of_urls") as mock_dl:
            qobuz.download_from_txt_file(str(txt_file))

            urls = mock_dl.call_args[0][0]
            assert urls == []

    def test_strips_newlines(self, qobuz, tmp_path):
        txt_file = tmp_path / "urls.txt"
        txt_file.write_text("https://play.qobuz.com/album/1\n")

        with patch.object(qobuz, "download_list_of_urls") as mock_dl:
            qobuz.download_from_txt_file(str(txt_file))

            urls = mock_dl.call_args[0][0]
            assert urls[0] == "https://play.qobuz.com/album/1"
            assert "\n" not in urls[0]

    def test_nonexistent_file_raises(self, qobuz):
        with pytest.raises(FileNotFoundError):
            qobuz.download_from_txt_file("/nonexistent/path.txt")
