import os
import subprocess
import time
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Spotify API credentials
SPOTIPY_CLIENT_ID = "c598dbc98954494389fb6a89de9ff6a3"
SPOTIPY_CLIENT_SECRET = "03746c236aa24f09a284525311dc4a8d"
SPOTIPY_REDIRECT_URI = "http://localhost:8888/callback"
HISTORY_PLAYLIST_ID = "2RVYDBfV3nu98qEb8ocPLA"
HISTORY_PLAYLIST_URI = f"spotify:playlist:{HISTORY_PLAYLIST_ID}"
MAX_RECENT_SONGS = 500

# Initialize Spotify client
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET,
    redirect_uri=SPOTIPY_REDIRECT_URI,
    scope="user-modify-playback-state user-read-playback-state user-read-recently-played user-library-modify user-library-read playlist-modify-public playlist-modify-private"
))

# Global variable to store recently played songs
recently_played_songs = []

def get_active_device():
    """Get the first active device"""
    try:
        devices = sp.devices()
        if not devices['devices']:
            return None
        return devices['devices'][0]['id']
    except Exception as e:
        print(f"Error getting active device: {str(e)}")
        return None

def add_to_history_playlist(track_uri):
    """Add a track to the history playlist if not already present"""
    try:
        # Check if the song is already in the playlist
        playlist_tracks = sp.playlist_tracks(HISTORY_PLAYLIST_ID, fields="items.track.uri")
        existing_uris = [item['track']['uri'] for item in playlist_tracks['items']]
        
        if track_uri not in existing_uris:
            sp.playlist_add_items(HISTORY_PLAYLIST_ID, [track_uri])
            return True
        return False
    except Exception as e:
        print(f"Error adding to history playlist: {str(e)}")
        return False

def update_recently_played():
    """Update the list of recently played songs and add to history playlist"""
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
                "uri": current_track["uri"]
            }
            
            # Check if the song is already in the list
            if not any(song['uri'] == new_song['uri'] for song in recently_played_songs):
                recently_played_songs.insert(0, new_song)
                if len(recently_played_songs) > MAX_RECENT_SONGS:
                    recently_played_songs = recently_played_songs[:MAX_RECENT_SONGS]
                
                add_to_history_playlist(current_track["uri"])
    except Exception as e:
        print(f"Error updating recently played: {str(e)}")

def check_and_rotate_playlist():
    """Check if we need to rotate back to the start of the playlist"""
    try:
        playback = sp.current_playback()
        if playback and playback.get('context') and playback['context']['type'] == 'playlist':
            playlist_uri = playback['context']['uri']
            playlist_id = playlist_uri.split(':')[-1]
            
            results = sp.playlist_tracks(playlist_id)
            tracks = results['items']
            while results['next']:
                results = sp.next(results)
                tracks.extend(results['items'])
            
            progress = playback.get('progress_ms', 0)
            duration = playback['item']['duration_ms'] if playback.get('item') else 0
            time_remaining = duration - progress
            
            if time_remaining < 5000 and playback.get('item'):
                current_uri = playback['item']['uri']
                current_index = next((i for i, item in enumerate(tracks) 
                                    if item['track']['uri'] == current_uri), -1)
                
                if current_index == len(tracks) - 1:
                    device_id = get_active_device()
                    if device_id:
                        sp.start_playback(
                            device_id=device_id,
                            context_uri=playlist_uri,
                            offset={"position": 0}
                        )
    except Exception as e:
        print(f"Error checking playlist rotation: {str(e)}")

def start_rotation_checker():
    """Background thread for checking playlist rotation"""
    while True:
        check_and_rotate_playlist()
        time.sleep(3)

# Start the rotation checker thread
rotation_thread = threading.Thread(target=start_rotation_checker)
rotation_thread.daemon = True
rotation_thread.start()

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

        current = sp.current_playback()
        if current and current.get('context') and current['context']['type'] == 'playlist':
            try:
                playlist_uri = current['context']['uri']
                playlist_id = playlist_uri.split(':')[-1]
                
                results = sp.playlist_tracks(playlist_id)
                tracks = results['items']
                while results['next']:
                    results = sp.next(results)
                    tracks.extend(results['items'])
                
                current_uri = current['item']['uri']
                current_index = next((i for i, item in enumerate(tracks) 
                                    if item['track']['uri'] == current_uri), -1)
                
                if current_index == len(tracks) - 1:
                    sp.start_playback(
                        device_id=device_id,
                        context_uri=playlist_uri,
                        offset={"position": 0}
                    )
                else:
                    sp.next_track(device_id=device_id)
            except Exception as e:
                print(f"Error handling playlist rotation: {str(e)}")
                sp.next_track(device_id=device_id)
        else:
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

        current = sp.current_playback()
        if current and current.get('context') and current['context']['uri'] == HISTORY_PLAYLIST_URI:
            sp.previous_track(device_id=device_id)
        else:
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
        context_uri = data.get("context_uri", HISTORY_PLAYLIST_URI)

        if not song_uri:
            return jsonify({"error": "No song URI provided"}), 400

        device_id = get_active_device()
        if not device_id:
            return jsonify({"error": "No active device found. Open Spotify on a device."}), 400

        if 'playlist' in context_uri:
            add_to_history_playlist(song_uri)
            
            results = sp.playlist_tracks(HISTORY_PLAYLIST_ID)
            track_uris = [item['track']['uri'] for item in results['items']]
            while results['next']:
                results = sp.next(results)
                track_uris.extend([item['track']['uri'] for item in results['items']])
            
            try:
                offset = track_uris.index(song_uri)
                sp.start_playback(
                    device_id=device_id,
                    context_uri=context_uri,
                    offset={"position": offset}
                )
            except ValueError:
                sp.start_playback(device_id=device_id, uris=[song_uri])
        else:
            sp.start_playback(device_id=device_id, uris=[song_uri])
        
        update_recently_played()
        return jsonify({"message": "Song playing"}), 200
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

        results = sp.playlist_tracks(HISTORY_PLAYLIST_ID)
        track_uris = [item['track']['uri'] for item in results['items']]
        while results['next']:
            results = sp.next(results)
            track_uris.extend([item['track']['uri'] for item in results['items']])
        
        try:
            offset = track_uris.index(song_uri)
        except ValueError:
            add_to_history_playlist(song_uri)
            results = sp.playlist_tracks(HISTORY_PLAYLIST_ID)
            track_uris = [item['track']['uri'] for item in results['items']]
            offset = track_uris.index(song_uri)

        sp.start_playback(
            device_id=device_id,
            context_uri=HISTORY_PLAYLIST_URI,
            offset={"position": offset}
        )
        
        update_recently_played()
        return jsonify({"message": "Playing from history playlist"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/current-song', methods=['GET'])
def get_current_song():
    try:
        current_playback = sp.current_playback()
        if not current_playback or not current_playback.get("item"):
            return jsonify({"error": "No song currently playing"}), 200

        current_track = current_playback["item"]
        return jsonify({
            "name": current_track["name"],
            "artist": current_track["artists"][0]["name"],
            "image": current_track["album"]["images"][0]["url"] if current_track["album"]["images"] else "",
            "uri": current_track["uri"]
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/recently-played', methods=['GET'])
def get_recently_played():
    try:
        # Get the last 50 tracks from Spotify's recently played
        results = sp.current_user_recently_played(limit=50)
        recent_tracks = []
        
        for item in results['items']:
            track = item['track']
            recent_tracks.append({
                "name": track["name"],
                "artist": track["artists"][0]["name"],
                "uri": track["uri"],
                "played_at": item["played_at"]
            })
        
        # Combine with our locally tracked recently played songs
        global recently_played_songs
        combined = recently_played_songs.copy()
        
        # Add Spotify's recently played that aren't already in our list
        for track in recent_tracks:
            if not any(s['uri'] == track['uri'] for s in combined):
                combined.append({
                    "name": track["name"],
                    "artist": track["artist"],
                    "uri": track["uri"],
                    "played_at": track["played_at"]
                })
        
        # Sort by play time (newest first)
        combined.sort(key=lambda x: x.get("played_at", ""), reverse=True)
        
        # Return only the most recent ones
        return jsonify({
            "recently_played": combined[:50]
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/volume-up', methods=['POST'])
def volume_up():
    try:
        device_id = get_active_device()
        if not device_id:
            return jsonify({"error": "No active device found"}), 400
            
        current_volume = sp.current_playback().get('device', {}).get('volume_percent', 50)
        new_volume = min(current_volume + 10, 100)
        sp.volume(new_volume, device_id=device_id)
        return jsonify({"message": f"Volume increased to {new_volume}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/volume-down', methods=['POST'])
def volume_down():
    try:
        device_id = get_active_device()
        if not device_id:
            return jsonify({"error": "No active device found"}), 400
            
        current_volume = sp.current_playback().get('device', {}).get('volume_percent', 50)
        new_volume = max(current_volume - 10, 0)
        sp.volume(new_volume, device_id=device_id)
        return jsonify({"message": f"Volume decreased to {new_volume}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/music-progress', methods=['GET'])
def get_music_progress():
    try:
        current_playback = sp.current_playback()
        if not current_playback or not current_playback.get("item"):
            return jsonify({"error": "No song currently playing"}), 200

        return jsonify({
            "progress": current_playback.get("progress_ms", 0),
            "duration": current_playback["item"]["duration_ms"]
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/seek', methods=['POST'])
def seek_position():
    try:
        data = request.get_json()
        position_ms = data.get("position_ms")
        
        if position_ms is None:
            return jsonify({"error": "No position provided"}), 400
            
        device_id = get_active_device()
        if not device_id:
            return jsonify({"error": "No active device found"}), 400
            
        sp.seek_track(position_ms, device_id=device_id)
        return jsonify({"message": f"Seeked to {position_ms}ms"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)