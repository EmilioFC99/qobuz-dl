#!/usr/bin/env python3
"""
One-time script to capture real Qobuz API responses as golden test fixtures.

Usage:
    python tests/capture_fixtures.py

Requires a valid config at ~/.config/qobuz-dl/config.ini with email/auth_token.
Run once, commit the resulting JSON files, and re-run only when you suspect
the API schema has changed.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from qobuz_dl.bundle import Bundle
from qobuz_dl import qopy

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
os.makedirs(FIXTURES_DIR, exist_ok=True)

FIELDS_TO_SCRUB = {"email", "firstname", "lastname", "display_name", "country_code"}


def scrub(obj):
    if isinstance(obj, dict):
        return {
            k: ("REDACTED" if k in FIELDS_TO_SCRUB else scrub(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [scrub(item) for item in obj]
    return obj


def save(name, data):
    path = os.path.join(FIXTURES_DIR, f"{name}.json")
    with open(path, "w") as f:
        json.dump(scrub(data), f, indent=2, ensure_ascii=False)
    print(f"  Saved {path} ({len(json.dumps(data))} bytes)")


def main():
    import configparser
    config = configparser.ConfigParser()
    config.read(os.path.expanduser("~/.config/qobuz-dl/config.ini"))

    section = "qobuz" if config.has_section("qobuz") else "DEFAULT"
    email = config.get(section, "email", fallback="")
    password = config.get(section, "password", fallback="")
    auth_token = (config.get(section, "user_auth_token", fallback="")
                  or config.get(section, "auth_token", fallback=""))
    app_id = config.get(section, "app_id", fallback="")
    secrets = [s for s in config.get(section, "secrets", fallback="").split(",") if s]

    if not app_id or not secrets:
        print("No app_id/secrets in config. Fetching from bundle...")
        bundle = Bundle()
        app_id = bundle.get_app_id()
        secrets = [s for s in bundle.get_secrets().values() if s]

    client = qopy.Client(email, password, app_id, secrets, auth_token)
    print("Authenticated. Capturing fixtures...\n")

    print("[catalog/search]")
    save("search_albums", client.search_albums("beethoven", limit=2))
    save("search_tracks", client.search_tracks("bohemian rhapsody", limit=2))
    save("search_artists", client.search_artists("radiohead", limit=2))
    save("search_playlists", client.search_playlists("chill", limit=2))

    print("\n[favorite/getUserFavorites]")
    save("get_favorites_albums", client.get_favorites(fav_type="albums", limit=2))
    save("get_favorites_tracks", client.get_favorites(fav_type="tracks", limit=2))

    print("\n[multi_meta endpoints]")
    for name, gen_fn, entity_id in [
        ("get_artist_meta", client.get_artist_meta, 36819),
        ("get_plist_meta", client.get_plist_meta, "1234567"),
        ("get_label_meta", client.get_label_meta, 9322512),
    ]:
        try:
            first_page = next(gen_fn(entity_id))
            save(name, first_page)
        except StopIteration:
            print(f"  WARNING: {name} returned no pages for id={entity_id}")
        except Exception as e:
            print(f"  ERROR capturing {name}: {e}")

    print("\nDone. Review the files in tests/fixtures/ and commit them.")
    print("Re-run this script if you suspect the API schema has changed.")


if __name__ == "__main__":
    main()
