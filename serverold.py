import os
import subprocess
from flask import Flask, request, jsonify
from flask_cors import CORS
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from datetime import datetime

app = Flask(__name__)
CORS(app)

SPOTIPY_CLIENT_ID = "aba284ab7d994a059898e8117293949a"
SPOTIPY_CLIENT_SECRET = "c3b4a65f814c4bc9a1c5f083082b8b6d"
SPOTIPY_REDIRECT_URI = "http://localhost:8888/callback"

# Updated scope with all required permissions
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET,
    redirect_uri=SPOTIPY_REDIRECT_URI,
    scope="user-modify-playback-state user-read-playback-state user-read-recently-played user-library-modify user-library-read playlist-modify-public playlist-modify-private"
))

# Global variable to store recently played songs
recently_played_songs = []

# Your personal playlist ID
MY_PLAYLIST_ID = "3cjnGjUALHAYZ8Pi2HWl2x"

def get_active_device():
    devices = sp.devices()
    if not devices['devices']:
        return None
    return devices['devices'][0]['id']

def update_recently_played():
    global recently_played_songs
    try:
        # Get the current playback
        current_playback = sp.current_playback()
        if current_playback and current_playback.get("item"):
            current_track = current_playback["item"]
            new_song = {
                "name": current_track["name"],
                "artist": current_track["artists"][0]["name"],
                "album": current_track["album"]["name"],
                "played_at": datetime.now().isoformat(),
                "uri": current_track["uri"],
                "is_liked": is_song_liked(current_track["uri"])
            }
            
            # Check if the song is already in the list
            if not any(song['uri'] == new_song['uri'] for song in recently_played_songs):
                recently_played_songs.insert(0, new_song)
                # Keep only the last 10 songs
                if len(recently_played_songs) > 10:
                    recently_played_songs = recently_played_songs[:10]
    except Exception as e:
        print(f"Error updating recently played: {str(e)}")

def is_song_liked(track_uri):
    """Check if a song is in your playlist or liked songs"""
    try:
        # Check if in your personal playlist
        playlist_tracks = sp.playlist_tracks(MY_PLAYLIST_ID)
        in_playlist = any(item['track']['uri'] == track_uri for item in playlist_tracks['items'])
        
        # Check if in liked songs
        liked = sp.current_user_saved_tracks_contains([track_uri])[0]
        
        return in_playlist or liked
    except Exception as e:
        print(f"Error checking liked status: {str(e)}")
        return False

@app.route('/start-scanning', methods=['POST'])
def start_scanning():
    try:
        script_path = os.path.abspath("emotion_spotify.py")

        if not os.path.exists(script_path):
            return jsonify({"error": f"File not found at {script_path}"}), 500

        process = subprocess.Popen(['python', script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()

        if stderr:
            return jsonify({"error": stderr.decode('utf-8')}), 500

        return jsonify({"message": "Face scanning started!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/play', methods=['POST'])
def play_song():
    try:
        device_id = get_active_device()
        if not device_id:
            return jsonify({"error": "No active device found. Open Spotify on a device."}), 400

        sp.start_playback(device_id=device_id)
        update_recently_played()
        return jsonify({"message": "Playback started"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/pause', methods=['POST'])
def pause_song():
    try:
        device_id = get_active_device()
        if not device_id:
            return jsonify({"error": "No active device found. Open Spotify on a device."}), 400

        sp.pause_playback(device_id=device_id)
        return jsonify({"message": "Playback paused"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/next', methods=['POST'])
def next_song():
    try:
        device_id = get_active_device()
        if not device_id:
            return jsonify({"error": "No active device found. Open Spotify on a device."}), 400

        sp.next_track(device_id=device_id)
        update_recently_played()
        return jsonify({"message": "Skipped to next track"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/previous', methods=['POST'])
def previous_song():
    try:
        device_id = get_active_device()
        if not device_id:
            return jsonify({"error": "No active device found. Open Spotify on a device."}), 400

        sp.previous_track(device_id=device_id)
        update_recently_played()
        return jsonify({"message": "Went back to previous track"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/current-playlist', methods=['GET'])
def get_current_playlist():
    try:
        current_track = sp.current_playback()
        if not current_track or not current_track.get("context"):
            return jsonify({"error": "No active playlist found"}), 400

        context = current_track["context"]
        if not context or "playlist" not in context["uri"]:
            return jsonify({"error": "Currently playing is not from a playlist"}), 400

        playlist_uri = context["uri"]
        playlist_id = playlist_uri.split(":")[-1]

        playlist = sp.playlist_tracks(playlist_id)

        songs = []
        for item in playlist["items"]:
            track = item["track"]
            songs.append({
                "name": track["name"],
                "artist": track["artists"][0]["name"],
                "uri": track["uri"]
            })

        return jsonify({"playlist": songs}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/play-song', methods=['POST'])
def play_selected_song():
    try:
        data = request.get_json()
        song_uri = data.get("uri")

        if not song_uri:
            return jsonify({"error": "No song URI provided"}), 400

        device_id = get_active_device()
        if not device_id:
            return jsonify({"error": "No active device found. Open Spotify on a device."}), 400

        sp.start_playback(device_id=device_id, uris=[song_uri])
        update_recently_played()
        return jsonify({"message": "Song playing"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/volume-up', methods=['POST'])
def volume_up():
    try:
        device_id = get_active_device()
        if not device_id:
            return jsonify({"error": "No active device found. Open Spotify on a device."}), 400

        current_volume = sp.current_playback().get("device", {}).get("volume_percent", 50)
        new_volume = min(current_volume + 10, 100)

        sp.volume(new_volume, device_id=device_id)
        return jsonify({"message": f"Volume increased to {new_volume}%"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/volume-down', methods=['POST'])
def volume_down():
    try:
        device_id = get_active_device()
        if not device_id:
            return jsonify({"error": "No active device found. Open Spotify on a device."}), 400

        current_volume = sp.current_playback().get("device", {}).get("volume_percent", 50)
        new_volume = max(current_volume - 10, 0)

        sp.volume(new_volume, device_id=device_id)
        return jsonify({"message": f"Volume decreased to {new_volume}%"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/current-song', methods=['GET'])
def current_song():
    try:
        current_track = sp.current_playback()
        if not current_track or not current_track.get("item"):
            return jsonify({"error": "No song currently playing"}), 400

        track = current_track["item"]
        song_data = {
            "name": track["name"],
            "artist": track["artists"][0]["name"],
            "album": track["album"]["name"],
            "image": track["album"]["images"][0]["url"] if track["album"]["images"] else "",
            "uri": track["uri"],
            "is_liked": is_song_liked(track["uri"])
        }
        return jsonify(song_data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/music-progress', methods=['GET'])
def get_music_progress():
    try:
        current_playback = sp.current_playback()
        if not current_playback or not current_playback.get("item"):
            return jsonify({"error": "No song currently playing"}), 400

        return jsonify({
            "progress": current_playback["progress_ms"],
            "duration": current_playback["item"]["duration_ms"]
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/seek', methods=['POST'])
def seek():
    try:
        data = request.get_json()
        position_ms = data.get("position_ms")

        if position_ms is None:
            return jsonify({"error": "No position provided"}), 400

        device_id = get_active_device()
        if not device_id:
            return jsonify({"error": "No active device found. Open Spotify on a device."}), 400

        sp.seek_track(position_ms, device_id=device_id)
        return jsonify({"message": f"Seeked to {position_ms} ms"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/recently-played', methods=['GET'])
def get_recently_played():
    try:
        # Return both Spotify's recently played and our local tracking
        spotify_recent = sp.current_user_recently_played(limit=10)
        combined = recently_played_songs.copy()

        # Add Spotify's recently played if not already in our list
        for item in spotify_recent["items"]:
            track = item["track"]
            song = {
                "name": track["name"],
                "artist": track["artists"][0]["name"],
                "album": track["album"]["name"],
                "played_at": item["played_at"],
                "uri": track["uri"],
                "is_liked": is_song_liked(track["uri"])
            }
            if not any(s['uri'] == song['uri'] for s in combined):
                combined.append(song)

        # Ensure we only return up to 10 items
        combined = combined[:10]
        return jsonify({"recently_played": combined}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/play-recent-song', methods=['POST'])
def play_recent_song():
    try:
        data = request.get_json()
        song_uri = data.get("uri")

        if not song_uri:
            return jsonify({"error": "No song URI provided"}), 400

        device_id = get_active_device()
        if not device_id:
            return jsonify({"error": "No active device found. Open Spotify on a device."}), 400

        sp.start_playback(device_id=device_id, uris=[song_uri])
        update_recently_played()
        return jsonify({"message": "Playing recently played song"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/like-song', methods=['POST'])
def like_song():
    """Add a song to both your playlist and liked songs"""
    try:
        data = request.get_json()
        song_uri = data.get('uri')

        if not song_uri:
            return jsonify({"error": "No song URI provided"}), 400

        # Add to your personal playlist
        sp.playlist_add_items(MY_PLAYLIST_ID, [song_uri])
        
        # Add to liked songs
        sp.current_user_saved_tracks_add([song_uri])
        
        # Update the liked status in recently played songs
        global recently_played_songs
        for song in recently_played_songs:
            if song['uri'] == song_uri:
                song['is_liked'] = True
                break
        
        return jsonify({
            
            "is_liked": True,
            "playlist_url": f"https://open.spotify.com/playlist/{MY_PLAYLIST_ID}"
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/dislike-song', methods=['POST'])
def dislike_song():
    """Remove a song from both your playlist and liked songs"""
    try:
        data = request.get_json()
        song_uri = data.get('uri')

        if not song_uri:
            return jsonify({"error": "No song URI provided"}), 400

        # Remove from your personal playlist
        sp.playlist_remove_all_occurrences_of_items(MY_PLAYLIST_ID, [song_uri])
        
        # Remove from liked songs
        sp.current_user_saved_tracks_delete([song_uri])
        
        # Update the liked status in recently played songs
        global recently_played_songs
        for song in recently_played_songs:
            if song['uri'] == song_uri:
                song['is_liked'] = False
                break
        
        return jsonify({
            
            "is_liked": False
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/get-playlist-url', methods=['GET'])
def get_playlist_url():
    try:
        return jsonify({
            "playlist_url": f"https://open.spotify.com/playlist/{MY_PLAYLIST_ID}"
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/create-playlist', methods=['POST'])
def create_playlist():
    try:
        data = request.get_json()
        playlist_name = data.get('name', f"My Playlist {datetime.now().strftime('%Y-%m-%d')}")
        song_uris = data.get('song_uris', [])
        
        user_id = sp.current_user()['id']
        
        playlist = sp.user_playlist_create(
            user=user_id,
            name=playlist_name,
            public=True,
            description="Automatically created playlist"
        )
        
        if song_uris:
            sp.playlist_add_items(playlist['id'], song_uris)
        
        return jsonify({
            "message": "Playlist created successfully",
            "playlist": {
                "id": playlist['id'],
                "name": playlist['name'],
                "uri": playlist['uri']
            }
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)