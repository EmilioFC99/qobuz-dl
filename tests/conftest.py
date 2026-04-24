import json
import os

import pytest
from unittest.mock import MagicMock, patch

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture(name):
    """Load a golden API response captured by capture_fixtures.py."""
    path = os.path.join(FIXTURES_DIR, f"{name}.json")
    if not os.path.exists(path):
        pytest.skip(
            f"Fixture file {name}.json not found. "
            "Run 'python tests/capture_fixtures.py' to capture real API responses."
        )
    with open(path) as f:
        return json.load(f)


@pytest.fixture
def mock_client():
    """A mock qopy.Client with common API methods stubbed."""
    client = MagicMock()
    client.search_albums.return_value = {"albums": {"items": []}}
    client.search_tracks.return_value = {"tracks": {"items": []}}
    client.search_artists.return_value = {"artists": {"items": []}}
    client.search_playlists.return_value = {"playlists": {"items": []}}
    client.get_favorites.return_value = {"albums": {"items": []}}
    client.get_plist_meta.return_value = iter([])
    client.get_artist_meta.return_value = iter([])
    client.get_label_meta.return_value = iter([])
    client.get_track_ids_from_list.return_value = []
    return client


@pytest.fixture
def qobuz(tmp_path, mock_client):
    """A QobuzDL instance with filesystem and DB side effects neutralized."""
    with patch("qobuz_dl.core.create_and_return_dir", return_value=str(tmp_path)):
        from qobuz_dl.core import QobuzDL
        instance = QobuzDL(
            directory=str(tmp_path),
            quality=6,
            downloads_db=None,
        )
    instance.client = mock_client
    return instance


@pytest.fixture
def sample_album_item():
    """A real album item extracted from a captured search_albums API response."""
    fixture = _load_fixture("search_albums")
    return fixture["albums"]["items"][0]


@pytest.fixture
def sample_track_item():
    """A real track item extracted from a captured search_tracks API response."""
    fixture = _load_fixture("search_tracks")
    return fixture["tracks"]["items"][0]


@pytest.fixture
def sample_artist_item():
    """A real artist item extracted from a captured search_artists API response."""
    fixture = _load_fixture("search_artists")
    return fixture["artists"]["items"][0]


@pytest.fixture
def sample_playlist_item():
    """A real playlist item extracted from a captured search_playlists API response."""
    fixture = _load_fixture("search_playlists")
    return fixture["playlists"]["items"][0]


@pytest.fixture
def sample_artist_meta():
    """A real artist/get response page captured from the API."""
    return _load_fixture("get_artist_meta")


@pytest.fixture
def sample_playlist_meta():
    """A real playlist/get response page captured from the API."""
    return _load_fixture("get_plist_meta")
