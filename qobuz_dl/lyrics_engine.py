import os
import requests
import mutagen
from mutagen.id3 import ID3, USLT, ID3NoHeaderError
from mutagen.flac import FLAC

# Importiamo lyricsgenius solo se l'utente ha configurato il token
try:
    import lyricsgenius
except ImportError:
    lyricsgenius = None

class LyricsEngine:
    def __init__(self, genius_token=None):
        self.genius_token = genius_token
        self.genius = None
        if self.genius_token and lyricsgenius:
            # Inizializziamo Genius in modalità silenziosa (verbose=False)
            self.genius = lyricsgenius.Genius(self.genius_token, verbose=False, remove_section_headers=True)

    def fetch_and_inject(self, file_path, artist, track, album):
        """Motore a cascata: prima prova LRCLIB (per il formato LRC), poi Genius."""
        try:
            print(f"    🔍 Cerco testo per: {track}...")
            
            # TENTATIVO 1: LRCLIB (Ricerca gratuita e priorità ai testi sincronizzati)
            lrclib_url = "https://lrclib.net/api/get"
            
            # Prova A: Ricerca precisissima (Artista + Traccia + Album)
            params = {"artist_name": artist, "track_name": track, "album_name": album}
            response = requests.get(lrclib_url, params=params, timeout=5) 
            
            # Prova B: Se fallisce, riproviamo ignorando l'album (spesso risolve i problemi di versioni/remastered)
            if response.status_code != 200:
                params = {"artist_name": artist, "track_name": track}
                response = requests.get(lrclib_url, params=params, timeout=5)

            if response.status_code == 200:
                data = response.json()
                synced_lyrics = data.get("syncedLyrics")
                plain_lyrics = data.get("plainLyrics")
                
                if synced_lyrics:
                    self._save_lrc_file(file_path, synced_lyrics)
                    self._inject_metadata(file_path, plain_lyrics)
                    print(f"    ✅ Testo Sincronizzato (Karaoke) salvato!")
                    return
                elif plain_lyrics:
                    self._inject_metadata(file_path, plain_lyrics)
                    print(f"    ✅ Testo standard iniettato nei metadati!")
                    return

            # TENTATIVO 2: FALLBACK SU GENIUS (Se l'utente ha messo il token)
            if self.genius:
                song = self.genius.search_song(track, artist)
                if song and song.lyrics:
                    self._inject_metadata(file_path, song.lyrics)
                    print(f"    ✅ Testo iniettato via Genius (Fallback)!")
                    return

            print(f"    ❌ Nessun testo trovato per questa traccia.")

        except Exception as e:
            print(f"    ⚠️ Errore durante la ricerca testi: {e}")

        except Exception as e:
            # Se la rete salta o l'API cambia, blocchiamo l'errore per salvare il file audio
            print(f"    ⚠️ Errore durante la ricerca testi: {e}")

    def _save_lrc_file(self, audio_file_path, synced_lyrics):
        """Crea il file .lrc affianco al file audio."""
        base_name = os.path.splitext(audio_file_path)[0]
        lrc_path = f"{base_name}.lrc"
        with open(lrc_path, 'w', encoding='utf-8') as f:
            f.write(synced_lyrics)

    def _inject_metadata(self, file_path, lyrics):
        """Inietta il testo direttamente nei tag del file FLAC o MP3."""
        if not lyrics: return
        
        ext = os.path.splitext(file_path)[1].lower()
        try:
            if ext == '.flac':
                audio = FLAC(file_path)
                audio['LYRICS'] = lyrics
                audio.save()
            elif ext == '.mp3':
                try:
                    audio = ID3(file_path)
                except ID3NoHeaderError:
                    audio = ID3()
                audio.add(USLT(encoding=3, lang='eng', desc='', text=lyrics))
                audio.save(file_path)
        except Exception:
            pass # Ignoriamo errori di scrittura per non bloccare il programma