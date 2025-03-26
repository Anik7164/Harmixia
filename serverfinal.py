import os
import subprocess
from flask import Flask, request, jsonify
from flask_cors import CORS
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from datetime import datetime, timedelta
import time

app = Flask(__name__)
CORS(app)

# Spotify API credentials
SPOTIPY_CLIENT_ID = "c598dbc98954494389fb6a89de9ff6a3"
SPOTIPY_CLIENT_SECRET = "03746c236aa24f09a284525311dc4a8d"
SPOTIPY_REDIRECT_URI = "http://localhost:3000/callback"

# Initialize Spotify client with required permissions
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET,
    redirect_uri=SPOTIPY_REDIRECT_URI,
    scope="user-modify-playback-state user-read-playback-state user-read-recently-played user-library-modify user-library-read playlist-modify-public playlist-modify-private"
))

# Global variables for tracking recently played songs
recently_played_songs = []
last_update_time = None
UPDATE_INTERVAL = 10  # Update interval in seconds (adjust as needed)

def get_active_device():
    """Get the currently active Spotify device"""
    devices = sp.devices()
    if not devices['devices']:
        return None
    return devices['devices'][0]['id']

def update_recently_played():
    """Update the list of recently played songs, but only every UPDATE_INTERVAL seconds"""
    global recently_played_songs, last_update_time
    
    current_time = time.time()
    if last_update_time and (current_time - last_update_time) < UPDATE_INTERVAL:
        return  # Skip update if not enough time has passed
    
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
                "image": current_track["album"]["images"][0]["url"] if current_track["album"]["images"] else ""
            }
            
            # Check if the song is already in the list
            if not any(song['uri'] == new_song['uri'] for song in recently_played_songs):
                recently_played_songs.insert(0, new_song)
                # Keep only the last 10 songs
                if len(recently_played_songs) > 10:
                    recently_played_songs = recently_played_songs[:10]
        
        last_update_time = current_time  # Update the last update time
    except Exception as e:
        print(f"Error updating recently played: {str(e)}")

@app.route('/start-scanning', methods=['POST'])
def start_scanning():
    """Endpoint to start the emotion scanning script"""
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
    """Endpoint to resume playback"""
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
    """Endpoint to pause playback"""
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
    """Endpoint to skip to next track"""
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
    """Endpoint to go back to previous track"""
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
    """Endpoint to get the current playlist"""
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
                "uri": track["uri"],
                "image": track["album"]["images"][0]["url"] if track["album"]["images"] else ""
            })

        return jsonify({"playlist": songs}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/play-song', methods=['POST'])
def play_selected_song():
    """Endpoint to play a specific song"""
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
    """Endpoint to increase volume"""
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
    """Endpoint to decrease volume"""
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
    """Endpoint to get the currently playing song"""
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
            "progress": current_track.get("progress_ms", 0),
            "duration": track["duration_ms"],
            "is_playing": current_track.get("is_playing", False)
        }
        return jsonify(song_data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/music-progress', methods=['GET'])
def get_music_progress():
    """Endpoint to get playback progress"""
    try:
        current_playback = sp.current_playback()
        if not current_playback or not current_playback.get("item"):
            return jsonify({"error": "No song currently playing"}), 400

        return jsonify({
            "progress": current_playback["progress_ms"],
            "duration": current_playback["item"]["duration_ms"],
            "is_playing": current_playback.get("is_playing", False)
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/seek', methods=['POST'])
def seek():
    """Endpoint to seek to a specific position in the track"""
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
    """Endpoint to get recently played songs"""
    try:
        # Update our local tracking before returning
        update_recently_played()
        
        # Return both our local tracking and Spotify's recently played
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
                "image": track["album"]["images"][0]["url"] if track["album"]["images"] else ""
            }
            if not any(s['uri'] == song['uri'] for s in combined):
                combined.append(song)

        # Ensure we only return up to 10 items, newest first
        combined = sorted(combined, key=lambda x: x.get('played_at', ''), reverse=True)[:10]
        return jsonify({"recently_played": combined}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/play-recent-song', methods=['POST'])
def play_recent_song():
    """Endpoint to play a recently played song"""
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

@app.route('/create-playlist', methods=['POST'])
def create_playlist():
    """Endpoint to create a new playlist"""
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
                "uri": playlist['uri'],
                "image": playlist['images'][0]['url'] if playlist['images'] else ""
            }
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
