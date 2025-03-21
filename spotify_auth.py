import spotipy
from spotipy.oauth2 import SpotifyOAuth

SPOTIPY_CLIENT_ID = "aba284ab7d994a059898e8117293949a"
SPOTIPY_CLIENT_SECRET = "c3b4a65f814c4bc9a1c5f083082b8b6d"
SPOTIPY_REDIRECT_URI = "http://localhost:8888/callback"

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET,
    redirect_uri=SPOTIPY_REDIRECT_URI,
    scope="user-modify-playback-state,user-read-playback-state"
))

print(sp.current_playback())
