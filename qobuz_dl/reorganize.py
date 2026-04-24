import os
import shutil
import logging

from mutagen.flac import FLAC
from mutagen.id3 import ID3

from qobuz_dl.color import CYAN, GREEN, RED, YELLOW, OFF
from qobuz_dl.downloader import process_folder_format_with_subdirs

logger = logging.getLogger(__name__)


def _read_tags_from_file(fpath):
    is_flac = fpath.lower().endswith('.flac')
    is_mp3 = fpath.lower().endswith('.mp3')
    if not is_flac and not is_mp3:
        return None

    try:
        if is_flac:
            audio = FLAC(fpath)
            return {
                "album_artist": ", ".join(audio.get("ALBUMARTIST", audio.get("ARTIST", [""]))),
                "album_title": ", ".join(audio.get("ALBUM", [""])),
                "year": ", ".join(audio.get("DATE", [""])).split("-")[0],
                "barcode": ", ".join(audio.get("BARCODE", [""])),
                "label": ", ".join(audio.get("LABEL", [""])),
                "album_id": ", ".join(audio.get("QOBUZALBUMID", [""])),
                "format": "FLAC",
                "bit_depth": getattr(audio.info, 'bits_per_sample', ""),
                "sampling_rate": round(audio.info.sample_rate / 1000, 1) if audio.info.sample_rate else "",
            }
        else:
            audio = ID3(fpath)
            album_artist = ""
            if audio.get("TPE2"):
                album_artist = audio["TPE2"].text[0]
            elif audio.get("TPE1"):
                album_artist = audio["TPE1"].text[0]

            album_title = audio["TALB"].text[0] if audio.get("TALB") else ""

            year = ""
            if audio.get("TDRC"):
                year = str(audio["TDRC"].text[0]).split("-")[0]

            barcode = ""
            if audio.get("TXXX:BARCODE"):
                barcode = audio["TXXX:BARCODE"].text[0]

            label = audio["TPUB"].text[0] if audio.get("TPUB") else ""

            album_id = ""
            if audio.get("TXXX:QOBUZALBUMID"):
                album_id = audio["TXXX:QOBUZALBUMID"].text[0]

            return {
                "album_artist": album_artist,
                "album_title": album_title,
                "year": year,
                "barcode": barcode,
                "label": label,
                "album_id": album_id,
                "format": "MP3",
                "bit_depth": "",
                "sampling_rate": "",
            }
    except Exception as e:
        logger.debug(f"Failed to read tags from {fpath}: {e}")
        return None


def _build_attr_dict(tags):
    return {
        "artist": tags.get("album_artist", ""),
        "album": tags.get("album_title", ""),
        "album_id": tags.get("album_id", ""),
        "album_url": "",
        "album_title": tags.get("album_title", ""),
        "album_title_base": tags.get("album_title", ""),
        "album_artist": tags.get("album_artist", ""),
        "album_genre": "",
        "album_composer": "",
        "label": tags.get("label", ""),
        "copyright": "",
        "upc": tags.get("barcode", ""),
        "barcode": tags.get("barcode", ""),
        "release_date": tags.get("year", ""),
        "year": tags.get("year", ""),
        "media_type": "",
        "format": tags.get("format", ""),
        "bit_depth": tags.get("bit_depth", ""),
        "sampling_rate": tags.get("sampling_rate", ""),
        "album_version": "",
        "version_tag": "",
        "disc_count": "",
        "track_count": "",
        "ExplicitFlag": "",
        "explicit": "",
        "release_type": "",
        "tracktitle": "",
        "track_title": "",
        "track_title_base": "",
    }


def _compute_moves(directory, folder_format):
    moves = []
    warnings = []

    for root, _, files in os.walk(directory):
        for fname in files:
            if not fname.lower().endswith(('.flac', '.mp3')):
                continue

            fpath = os.path.join(root, fname)
            tags = _read_tags_from_file(fpath)

            if tags is None:
                warnings.append(f"Could not read tags: {fpath}")
                continue

            if not tags.get("album_artist") or not tags.get("album_title"):
                warnings.append(f"Missing album_artist or album_title: {fpath}")
                continue

            attr_dict = _build_attr_dict(tags)
            target_subdir = process_folder_format_with_subdirs(folder_format, attr_dict)
            dst = os.path.join(directory, target_subdir, fname)

            if os.path.normpath(fpath) == os.path.normpath(dst):
                continue

            moves.append((fpath, dst))

            lrc_src = os.path.splitext(fpath)[0] + ".lrc"
            if os.path.isfile(lrc_src):
                lrc_dst = os.path.splitext(dst)[0] + ".lrc"
                moves.append((lrc_src, lrc_dst))

    return moves, warnings


def _cleanup_empty_dirs(directory):
    for root, dirs, files in os.walk(directory, topdown=False):
        if root == directory:
            continue
        if not os.listdir(root):
            os.rmdir(root)


def reorganize_folder(directory, by_album, folder_format, auto_confirm=False, dry_run=False):
    directory = os.path.abspath(directory)

    if not os.path.isdir(directory):
        logger.error(f"{RED}Directory does not exist: {directory}{OFF}")
        return

    logger.info(f"\n{YELLOW}━━━ REORGANIZE ━━━{OFF}")
    logger.info(f"{YELLOW}DIR    : {directory}{OFF}")
    logger.info(f"{YELLOW}FORMAT : {folder_format}{OFF}")
    logger.info(f"{YELLOW}MODE   : by-album{OFF}\n")

    logger.info(f"{CYAN}[1/3] Scanning files and computing moves...{OFF}")
    moves, warnings = _compute_moves(directory, folder_format)

    if warnings:
        logger.info(f"\n{YELLOW}Warnings ({len(warnings)}):{OFF}")
        for w in warnings:
            logger.info(f"  {YELLOW}! {w}{OFF}")

    if not moves:
        logger.info(f"\n{GREEN}All files are already organized. Nothing to do.{OFF}")
        return

    logger.info(f"\n{CYAN}[2/3] Move plan ({len(moves)} files):{OFF}")
    for src, dst in moves:
        rel_src = os.path.relpath(src, directory)
        rel_dst = os.path.relpath(dst, directory)
        logger.info(f"  {rel_src}  ->  {GREEN}{rel_dst}{OFF}")

    if dry_run:
        logger.info(f"\n{YELLOW}Dry run — no files were moved.{OFF}")
        return

    if not auto_confirm:
        try:
            answer = input(f"\n{YELLOW}Proceed with reorganization? [y/N]: {OFF}").strip().lower()
            if answer != 'y':
                logger.info(f"{YELLOW}Reorganization cancelled.{OFF}")
                return
        except (KeyboardInterrupt, EOFError):
            logger.info(f"\n{YELLOW}Reorganization cancelled.{OFF}")
            return

    logger.info(f"\n{CYAN}[3/3] Moving files...{OFF}")
    moved = 0
    skipped = 0
    for src, dst in moves:
        if os.path.exists(dst):
            logger.info(f"  {YELLOW}[skip] Already exists: {os.path.relpath(dst, directory)}{OFF}")
            skipped += 1
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
        moved += 1
        logger.info(f"  {GREEN}[ok] {os.path.relpath(dst, directory)}{OFF}")

    _cleanup_empty_dirs(directory)

    logger.info(f"\n{GREEN}━━━ REORGANIZE COMPLETE ━━━{OFF}")
    logger.info(f"  {GREEN}Moved   : {moved} files{OFF}")
    if skipped:
        logger.info(f"  {YELLOW}Skipped : {skipped} files (already exist at destination){OFF}")
    if warnings:
        logger.info(f"  {YELLOW}Warnings: {len(warnings)} files could not be processed{OFF}")
    logger.info("")
