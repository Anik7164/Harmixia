import os
import json
import subprocess
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Configuration
CONFIG = {
    "SPOTIPY_CLIENT_ID": "c598dbc98954494389fb6a89de9ff6a3",
    "SPOTIPY_CLIENT_SECRET": "03746c236aa24f09a284525311dc4a8d",
    "SPOTIPY_REDIRECT_URI": "http://localhost:3000/callback",
    "RECENTLY_PLAYED_FILE": "recently_played.json",
    "LIKED_PLAYLIST_URI": "spotify:playlist:7bAgQ9YR6GdKhKdTXvFyBl",
    "EMOTION_LABELS": {
        1: "nothing",
        2: "happy",
        3: "sad",
        4: "angry",
        5: "neutral"
    }
}


sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=CONFIG["SPOTIPY_CLIENT_ID"],
    client_secret=CONFIG["SPOTIPY_CLIENT_SECRET"],
    redirect_uri=CONFIG["SPOTIPY_REDIRECT_URI"],
    scope="user-modify-playback-state user-read-playback-state user-read-recently-played playlist-modify-public playlist-modify-private playlist-read-private"
))


current_emotion = 1  
recently_played_songs = []


def load_recently_played():
    """Load recently played songs from JSON file"""
    try:
        if os.path.exists(CONFIG["RECENTLY_PLAYED_FILE"]):
            with open(CONFIG["RECENTLY_PLAYED_FILE"], 'r') as f:
                return json.load(f)
    except Exception as e:
        app.logger.error(f"Error loading recently played: {str(e)}")
    return []

def save_recently_played(songs):
    """Save recently played songs to JSON file"""
    try:
        with open(CONFIG["RECENTLY_PLAYED_FILE"], 'w') as f:
            json.dump(songs, f)
    except Exception as e:
        app.logger.error(f"Error saving recently played: {str(e)}")

def requires_device(f):
    """Decorator to check for active device"""
    @wraps(f)
    def decorated(*args, **kwargs):
        device_id = get_active_device()
        if not device_id:
            return jsonify({"error": "No active device found. Open Spotify on a device."}), 400
        return f(device_id, *args, **kwargs)
    return decorated

def get_active_device():
    """Get the first active Spotify device"""
    try:
        devices = sp.devices()
        return devices['devices'][0]['id'] if devices['devices'] else None
    except Exception as e:
        app.logger.error(f"Error getting active device: {str(e)}")
        return None

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
            
            
            recently_played_songs = [
                song for song in recently_played_songs 
                if song['uri'] != new_song['uri']
            ][:9]
            recently_played_songs.insert(0, new_song)
            
            save_recently_played(recently_played_songs)
    except Exception as e:
        app.logger.error(f"Error updating recently played: {str(e)}")

def get_liked_tracks():
    """Get all tracks from the liked playlist"""
    try:
        playlist_id = CONFIG["LIKED_PLAYLIST_URI"].split(":")[-1]
        results = sp.playlist_tracks(playlist_id)
        tracks = results['items']
        
        while results['next']:
            results = sp.next(results)
            tracks.extend(results['items'])
            
        return [item['track']['uri'] for item in tracks]
    except Exception as e:
        app.logger.error(f"Error getting liked tracks: {str(e)}")
        return []


recently_played_songs = load_recently_played()


@app.route('/update-emotion', methods=['POST'])
def update_emotion():
    """Receive emotion updates from the emotion detection script"""
    global current_emotion
    try:
        data = request.get_json()
        current_emotion = data.get('emotion', 1)
        app.logger.info(f"Emotion updated to {CONFIG['EMOTION_LABELS'].get(current_emotion, 'unknown')}")
        return jsonify({"success": True}), 200
    except Exception as e:
        app.logger.error(f"Error updating emotion: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/current-emotion', methods=['GET'])
def get_current_emotion():
    """Get the current detected emotion"""
    return jsonify({
        "emotion": current_emotion,
        "label": CONFIG["EMOTION_LABELS"].get(current_emotion, "unknown")
    }), 200

@app.route('/start-scanning', methods=['POST'])
def start_scanning():
    """Start emotion detection script"""
    try:
        script_path = os.path.abspath("emotion_spotify.py")
        if not os.path.exists(script_path):
            return jsonify({"error": f"File not found at {script_path}"}), 404

        process = subprocess.Popen(['python', script_path], 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()

        if stderr:
            app.logger.error(stderr.decode('utf-8'))
            return jsonify({"error": "Error starting scanning"}), 500
            
        return jsonify({"message": "Face scanning started!"}), 200
    except Exception as e:
        app.logger.error(f"Error starting scanning: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/play', methods=['POST'])
@requires_device
def play_song(device_id):
    """Resume playback"""
    try:
        sp.start_playback(device_id=device_id)
        update_recently_played()
        return jsonify({"message": "Playback started"}), 200
    except Exception as e:
        app.logger.error(f"Error starting playback: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/pause', methods=['POST'])
@requires_device
def pause_song(device_id):
    """Pause playback"""
    try:
        sp.pause_playback(device_id=device_id)
        return jsonify({"message": "Playback paused"}), 200
    except Exception as e:
        app.logger.error(f"Error pausing playback: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/next', methods=['POST'])
@requires_device
def next_song(device_id):
    """Skip to next track"""
    try:
        sp.next_track(device_id=device_id)
        update_recently_played()
        return jsonify({"message": "Skipped to next track"}), 200
    except Exception as e:
        app.logger.error(f"Error skipping track: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/previous', methods=['POST'])
@requires_device
def previous_song(device_id):
    """Go back to previous track"""
    try:
        sp.previous_track(device_id=device_id)
        update_recently_played()
        return jsonify({"message": "Went back to previous track"}), 200
    except Exception as e:
        app.logger.error(f"Error going to previous track: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/current-playlist', methods=['GET'])
def get_current_playlist():
    """Get current playlist tracks"""
    try:
        playlist_uri = request.args.get('playlist_uri')
        
        if playlist_uri:
            playlist_id = playlist_uri.split(":")[-1]
        else:
            current_track = sp.current_playback()
            if not current_track or not current_track.get("context"):
                return jsonify({"error": "No active playlist found"}), 404

            context = current_track["context"]
            if not context or "playlist" not in context["uri"]:
                return jsonify({"error": "Currently playing is not from a playlist"}), 400

            playlist_uri = context["uri"]
            playlist_id = playlist_uri.split(":")[-1]

        playlist = sp.playlist_tracks(playlist_id)
        liked_uris = get_liked_tracks()

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
        app.logger.error(f"Error getting current playlist: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/play-song', methods=['POST'])
@requires_device
def play_selected_song(device_id):
    """Play specific song"""
    try:
        data = request.get_json()
        song_uri = data.get("uri")
        context_uri = data.get("context_uri")

        if not song_uri:
            return jsonify({"error": "No song URI provided"}), 400

        if context_uri:
            playlist_id = context_uri.split(":")[-1]
            playlist_tracks = sp.playlist_tracks(playlist_id)
            
            offset = next(
                (i for i, item in enumerate(playlist_tracks["items"]) 
                if item["track"]["uri"] == song_uri
            ), 0)
            
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
        app.logger.error(f"Error playing selected song: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/volume-up', methods=['POST'])
@requires_device
def volume_up(device_id):
    """Increase volume"""
    try:
        current_volume = sp.current_playback().get("device", {}).get("volume_percent", 50)
        new_volume = min(current_volume + 10, 100)
        sp.volume(new_volume, device_id=device_id)
        return jsonify({"message": f"Volume increased to {new_volume}%"}), 200
    except Exception as e:
        app.logger.error(f"Error increasing volume: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/volume-down', methods=['POST'])
@requires_device
def volume_down(device_id):
    """Decrease volume"""
    try:
        current_volume = sp.current_playback().get("device", {}).get("volume_percent", 50)
        new_volume = max(current_volume - 10, 0)
        sp.volume(new_volume, device_id=device_id)
        return jsonify({"message": f"Volume decreased to {new_volume}%"}), 200
    except Exception as e:
        app.logger.error(f"Error decreasing volume: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/current-song', methods=['GET'])
def current_song():
    """Get currently playing track info"""
    try:
        current_track = sp.current_playback()
        if not current_track or not current_track.get("item"):
            return jsonify({"error": "No song currently playing"}), 404

        track = current_track["item"]
        liked_uris = get_liked_tracks()
        
        return jsonify({
            "name": track["name"],
            "artist": track["artists"][0]["name"],
            "album": track["album"]["name"],
            "image": track["album"]["images"][0]["url"] if track["album"]["images"] else "",
            "uri": track["uri"],
            "is_playing": current_track.get("is_playing", False),
            "is_liked": track["uri"] in liked_uris
        }), 200
    except Exception as e:
        app.logger.error(f"Error getting current song: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/music-progress', methods=['GET'])
def get_music_progress():
    """Get current playback progress"""
    try:
        current_playback = sp.current_playback()
        if not current_playback or not current_playback.get("item"):
            return jsonify({"error": "No song currently playing"}), 404

        return jsonify({
            "progress": current_playback["progress_ms"],
            "duration": current_playback["item"]["duration_ms"],
            "is_playing": current_playback.get("is_playing", False)
        }), 200
    except Exception as e:
        app.logger.error(f"Error getting music progress: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/seek', methods=['POST'])
@requires_device
def seek(device_id):
    """Seek to position in track"""
    try:
        position_ms = request.get_json().get("position_ms")
        if position_ms is None:
            return jsonify({"error": "No position provided"}), 400

        sp.seek_track(position_ms, device_id=device_id)
        return jsonify({"message": f"Seeked to {position_ms} ms"}), 200
    except Exception as e:
        app.logger.error(f"Error seeking track: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/recently-played', methods=['GET'])
def get_recently_played():
    """Get combined recently played songs"""
    try:
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
            if not any(s['uri'] == song['uri'] for s in recently_played_songs):
                combined.append(song)

        combined.sort(key=lambda x: x.get('played_at', ''), reverse=True)
        return jsonify({"recently_played": combined[:10]}), 200
    except Exception as e:
        app.logger.error(f"Error getting recently played: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/play-recent-song', methods=['POST'])
@requires_device
def play_recent_song(device_id):
    """Play a song from recently played list"""
    try:
        song_uri = request.get_json().get("uri")
        if not song_uri:
            return jsonify({"error": "No song URI provided"}), 400

        sp.start_playback(device_id=device_id, uris=[song_uri])
        update_recently_played()
        return jsonify({"message": "Playing recently played song"}), 200
    except Exception as e:
        app.logger.error(f"Error playing recent song: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/check-song-in-playlist', methods=['GET'])
def check_song_in_playlist():
    """Check if a song is in the specified playlist"""
    try:
        song_uri = request.args.get('song_uri')
        playlist_uri = request.args.get('playlist_uri', CONFIG["LIKED_PLAYLIST_URI"])
        
        if not song_uri:
            return jsonify({"error": "No song URI provided"}), 400
            
        playlist_id = playlist_uri.split(":")[-1]
        results = sp.playlist_tracks(playlist_id)
        
        is_in_playlist = any(
            item['track']['uri'] == song_uri 
            for item in results['items']
        )
        
        return jsonify({
            "is_in_playlist": is_in_playlist,
            "message": "Song is in playlist" if is_in_playlist else "Song is not in playlist"
        }), 200
        
    except Exception as e:
        app.logger.error(f"Error checking song in playlist: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/like-song', methods=['POST'])
def like_song():
    """Add song to the specific liked playlist"""
    try:
        song_uri = request.get_json().get("uri")
        if not song_uri:
            return jsonify({"error": "No song URI provided"}), 400
            
        playlist_id = CONFIG["LIKED_PLAYLIST_URI"].split(":")[-1]
        liked_uris = get_liked_tracks()
        
        if song_uri in liked_uris:
            return jsonify({
                "success": False,
                "message": "Song is already in liked playlist"
            }), 200
        
        sp.playlist_add_items(playlist_id, [song_uri])
        
        return jsonify({
            "success": True,
            "message": "Song added to liked playlist"
        }), 200
    except Exception as e:
        app.logger.error(f"Error liking song: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/dislike-song', methods=['POST'])
def dislike_song():
    """Remove song from the specific liked playlist"""
    try:
        song_uri = request.get_json().get("uri")
        if not song_uri:
            return jsonify({"error": "No song URI provided"}), 400
            
        playlist_id = CONFIG["LIKED_PLAYLIST_URI"].split(":")[-1]
        liked_uris = get_liked_tracks()
        
        if song_uri not in liked_uris:
            return jsonify({
                "success": False,
                "message": "Song not found in liked playlist"
            }), 200
            
        
        results = sp.playlist_tracks(playlist_id)
        track_to_remove = next(
            ({"uri": item['track']['uri'], "positions": [item['track']['track_number'] - 1]}
             for item in results['items'] if item['track']['uri'] == song_uri),
            None
        )
                
        if track_to_remove:
            sp.playlist_remove_specific_occurrences_of_items(
                playlist_id,
                [track_to_remove]
            )
        
        return jsonify({
            "success": True,
            "message": "Song removed from liked playlist"
        }), 200
    except Exception as e:
        app.logger.error(f"Error disliking song: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)