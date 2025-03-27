import os
import json
import subprocess
from flask import Flask, request, jsonify
from flask_cors import CORS
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Spotify API credentials
SPOTIPY_CLIENT_ID = "73cecce44b3d4e2ebd39a9070b4105b2"
SPOTIPY_CLIENT_SECRET = "37d2b33649644775a1960817b224e9c6"
SPOTIPY_REDIRECT_URI = "http://localhost:8888/callback"

# File to store recently played songs
RECENTLY_PLAYED_FILE = "recently_played.json"

# Specific liked playlist URI
LIKED_PLAYLIST_URI = "spotify:playlist:6B73TSXPjWR1H6oYvb1MKg"

# Initialize Spotify client
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET,
    redirect_uri=SPOTIPY_REDIRECT_URI,
    scope="user-modify-playback-state user-read-playback-state user-read-recently-played playlist-modify-public playlist-modify-private playlist-read-private"
))

def load_recently_played():
    """Load recently played songs from JSON file"""
    try:
        if os.path.exists(RECENTLY_PLAYED_FILE):
            with open(RECENTLY_PLAYED_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading recently played: {str(e)}")
    return []

def save_recently_played(songs):
    """Save recently played songs to JSON file"""
    try:
        with open(RECENTLY_PLAYED_FILE, 'w') as f:
            json.dump(songs, f)
    except Exception as e:
        print(f"Error saving recently played: {str(e)}")

# Initialize with loaded data
recently_played_songs = load_recently_played()

def get_active_device():
    """Get the first active Spotify device"""
    devices = sp.devices()
    if not devices['devices']:
        return None
    return devices['devices'][0]['id']

def update_recently_played():
    """Update the list of recently played songs"""
    global recently_played_songs
    try:
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
            
            # Remove if already exists (to avoid duplicates)
            recently_played_songs = [song for song in recently_played_songs if song['uri'] != new_song['uri']]
            
            # Add to beginning of list
            recently_played_songs.insert(0, new_song)
            
            # Keep only the 10 most recent
            recently_played_songs = recently_played_songs[:10]
            save_recently_played(recently_played_songs)
    except Exception as e:
        print(f"Error updating recently played: {str(e)}")

@app.route('/start-scanning', methods=['POST'])
def start_scanning():
    """Start emotion detection script"""
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
    """Resume playback"""
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
    """Pause playback"""
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
    """Skip to next track"""
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
    """Go back to previous track"""
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
    """Get current playlist tracks"""
    try:
        playlist_uri = request.args.get('playlist_uri')
        
        if playlist_uri:
            # Fetch the specified playlist
            playlist_id = playlist_uri.split(":")[-1]
        else:
            # Fetch current playlist from playback context
            current_track = sp.current_playback()
            if not current_track or not current_track.get("context"):
                return jsonify({"error": "No active playlist found"}), 400

            context = current_track["context"]
            if not context or "playlist" not in context["uri"]:
                return jsonify({"error": "Currently playing is not from a playlist"}), 400

            playlist_uri = context["uri"]
            playlist_id = playlist_uri.split(":")[-1]

        playlist = sp.playlist_tracks(playlist_id)

        # Get liked songs to check which are already liked
        liked_playlist_id = LIKED_PLAYLIST_URI.split(":")[-1]
        liked_tracks = sp.playlist_tracks(liked_playlist_id)
        liked_uris = [item['track']['uri'] for item in liked_tracks['items']]

        songs = []
        for item in playlist["items"]:
            track = item["track"]
            songs.append({
                "name": track["name"],
                "artist": track["artists"][0]["name"],
                "uri": track["uri"],
                "image": track["album"]["images"][0]["url"] if track["album"]["images"] else "",
                "is_liked": track["uri"] in liked_uris
            })

        return jsonify({
            "playlist": songs,
            "playlist_uri": playlist_uri
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/play-song', methods=['POST'])
def play_selected_song():
    """Play specific song"""
    try:
        data = request.get_json()
        song_uri = data.get("uri")
        context_uri = data.get("context_uri", None)

        if not song_uri:
            return jsonify({"error": "No song URI provided"}), 400

        device_id = get_active_device()
        if not device_id:
            return jsonify({"error": "No active device found. Open Spotify on a device."}), 400

        if context_uri:
            playlist_id = context_uri.split(":")[-1]
            playlist_tracks = sp.playlist_tracks(playlist_id)
            
            offset = 0
            for i, item in enumerate(playlist_tracks["items"]):
                if item["track"]["uri"] == song_uri:
                    offset = i
                    break
            
            sp.start_playback(
                device_id=device_id,
                context_uri=context_uri,
                offset={"position": offset}
            )
        else:
            sp.start_playback(device_id=device_id, uris=[song_uri])
            
        update_recently_played()
        return jsonify({"message": "Song playing"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/volume-up', methods=['POST'])
def volume_up():
    """Increase volume"""
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
    """Decrease volume"""
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
    """Get currently playing track info"""
    try:
        current_track = sp.current_playback()
        if not current_track or not current_track.get("item"):
            return jsonify({"error": "No song currently playing"}), 400

        track = current_track["item"]
        
        # Check if song is in liked playlist
        liked_playlist_id = LIKED_PLAYLIST_URI.split(":")[-1]
        liked_tracks = sp.playlist_tracks(liked_playlist_id)
        is_liked = any(item['track']['uri'] == track['uri'] for item in liked_tracks['items'])
        
        song_data = {
            "name": track["name"],
            "artist": track["artists"][0]["name"],
            "album": track["album"]["name"],
            "image": track["album"]["images"][0]["url"] if track["album"]["images"] else "",
            "uri": track["uri"],
            "is_playing": current_track.get("is_playing", False),
            "is_liked": is_liked
        }
        return jsonify(song_data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/music-progress', methods=['GET'])
def get_music_progress():
    """Get current playback progress"""
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
    """Seek to position in track"""
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
    """Get combined recently played songs"""
    try:
        # Combine our tracked recently played with Spotify's API
        spotify_recent = sp.current_user_recently_played(limit=10)
        combined = recently_played_songs.copy()

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
            # Only add if not already in our tracked recently played
            if not any(s['uri'] == song['uri'] for s in recently_played_songs):
                combined.append(song)

        # Sort by played_at (newest first) and return only 10
        combined.sort(key=lambda x: x.get('played_at', ''), reverse=True)
        return jsonify({"recently_played": combined[:10]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/play-recent-song', methods=['POST'])
def play_recent_song():
    """Play a song from recently played list"""
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

@app.route('/check-song-in-playlist', methods=['GET'])
def check_song_in_playlist():
    """Check if a song is in the specified playlist"""
    try:
        song_uri = request.args.get('song_uri')
        playlist_uri = request.args.get('playlist_uri', LIKED_PLAYLIST_URI)
        
        if not song_uri:
            return jsonify({"error": "No song URI provided"}), 400
            
        playlist_id = playlist_uri.split(":")[-1]
        
        # Check if the song exists in the playlist
        results = sp.playlist_tracks(playlist_id)
        for item in results['items']:
            if item['track']['uri'] == song_uri:
                return jsonify({
                    "is_in_playlist": True,
                    "message": "Song is in playlist"
                }), 200
                
        return jsonify({
            "is_in_playlist": False,
            "message": "Song is not in playlist"
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/like-song', methods=['POST'])
def like_song():
    """Add song to the specific liked playlist"""
    try:
        data = request.get_json()
        song_uri = data.get("uri")
        
        if not song_uri:
            return jsonify({"error": "No song URI provided"}), 400
            
        playlist_id = LIKED_PLAYLIST_URI.split(":")[-1]
        
        # First check if song is already in playlist
        results = sp.playlist_tracks(playlist_id)
        for item in results['items']:
            if item['track']['uri'] == song_uri:
                return jsonify({
                    "success": False,
                    "message": "Song is already in liked playlist"
                }), 200
        
        # Add the song to the playlist
        sp.playlist_add_items(playlist_id, [song_uri])
        
        return jsonify({
            "success": True,
            "message": "Song added to liked playlist"
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/dislike-song', methods=['POST'])
def dislike_song():
    """Remove song from the specific liked playlist"""
    try:
        data = request.get_json()
        song_uri = data.get("uri")
        
        if not song_uri:
            return jsonify({"error": "No song URI provided"}), 400
            
        playlist_id = LIKED_PLAYLIST_URI.split(":")[-1]
        
        # Get all tracks in the playlist to find the specific occurrence
        tracks = []
        results = sp.playlist_tracks(playlist_id)
        tracks.extend(results['items'])
        
        while results['next']:
            results = sp.next(results)
            tracks.extend(results['items'])
        
        # Find the track to remove
        track_to_remove = None
        for item in tracks:
            if item['track']['uri'] == song_uri:
                track_to_remove = {
                    "uri": item['track']['uri'],
                    "positions": [item['track']['track_number'] - 1]
                }
                break
                
        if not track_to_remove:
            return jsonify({
                "success": False,
                "message": "Song not found in liked playlist"
            }), 200
            
        # Remove the track
        sp.playlist_remove_specific_occurrences_of_items(
            playlist_id,
            [track_to_remove]
        )
        
        return jsonify({
            "success": True,
            "message": "Song removed from liked playlist"
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)