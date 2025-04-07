import cv2
import time
import requests
import argparse
from collections import Counter
from deepface import DeepFace
from spotify_auth import sp  # Your Spotify authentication module

# Face detection setup
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# Emotion mappings
EMOTION_MAP = {
    "happy": 2,
    "sad": 3,
    "angry": 4,
    "neutral": 5,
    "nothing": 1  # Default when no face detected
}

# Color mappings for each emotion (BGR format)
EMOTION_COLORS = {
    "happy": (0, 255, 255),    # Yellow
    "sad": (255, 0, 0),        # Blue
    "angry": (0, 0, 255),      # Red
    "neutral": (0, 255, 0),    # Green
    "nothing": (128, 128, 128) # Gray
}

PLAYLIST_MAP = {
    2: "spotify:playlist:1AJZcd3ZlMhq2DBYVI8z7a",  # Happy
    3: "spotify:playlist:6RugFKjNj9dIGlFhHrZjvD",  # Sad
    4: "spotify:playlist:08Kr4pW2Cgmb7F0bBRZn1Z",  # Angry
    5: "spotify:playlist:7crckZBjA169XB6W1dFKSh"   # Neutral
}

class EmotionDetector:
    def __init__(self):
        self.last_emotion_sent = 1  # Start with "nothing"
        self.scanning = False
        self.cap = None
        self.start_time = 0
        self.last_playback_check = 0
        self.current_emotion = "nothing"
        self.emotion_window = []
        self.last_playback_state = False
        self.last_detected_emotion = None
        self.pause_mode = False  # New flag for pause-and-detect mode
        self.pause_detection_interval = 3  # Seconds between pause checks
            
    def start_scanning(self, pause_mode=False):
        """Initialize camera and start scanning"""
        if not self.scanning:
            self.cap = cv2.VideoCapture(0)
            self.scanning = True
            self.start_time = time.time()
            self.emotion_window = []
            self.pause_mode = pause_mode
            print("Starting emotion scanning in 3 seconds...")
            send_emotion_update(1, 0.0)  # Reset to "nothing"
            return True
        return False
            
    def stop_scanning(self):
        """Release camera and stop scanning"""
        if self.scanning:
            self.cap.release()
            cv2.destroyAllWindows()
            self.scanning = False
            print("Stopped emotion scanning")
            return True
        return False
            
    def detect_emotion(self):
        """Perform single detection cycle when scanning is active"""
        if not self.scanning:
            return
            
        # Check if 5 seconds have passed since starting
        if time.time() - self.start_time < 3:
            remaining = 3 - int(time.time() - self.start_time)
            ret, frame = self.cap.read()
            if ret:
                cv2.putText(frame, f"Starting in {remaining} seconds...", 
                          (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.imshow('Emotion Detection', frame)
            return
            
        ret, frame = self.cap.read()
        if not ret:
            return
            
        # Convert frame for processing
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Detect faces
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        current_emotion_num = 1  # Default to "nothing"
        max_confidence = 0
        detected_emotion = "nothing"

        if len(faces) > 0:
            # Analyze each face
            for (x, y, w, h) in faces:
                try:
                    result = DeepFace.analyze(rgb[y:y+h, x:x+w], actions=['emotion'], enforce_detection=False)
                    emotion = result[0]['dominant_emotion']
                    confidence = result[0]['emotion'][emotion]/100
                    
                    if confidence > max_confidence:
                        detected_emotion = emotion
                        current_emotion_num = EMOTION_MAP.get(emotion, 1)
                        max_confidence = confidence

                    # Get color for detected emotion
                    color = EMOTION_COLORS.get(emotion, (128, 128, 128))
                    
                    # Draw visualization with emotion-specific color
                    cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
                    cv2.putText(frame, f"{emotion} ({confidence:.0%})", 
                              (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
                except Exception as e:
                    continue

        # Update current emotion and maintain window
        self.current_emotion = detected_emotion
        if detected_emotion != "nothing":
            self.emotion_window.append(current_emotion_num)
            if len(self.emotion_window) > 5:
                self.emotion_window.pop(0)
        
        # Display current emotion in corner
        status_color = EMOTION_COLORS.get(self.current_emotion, (128, 128, 128))
        cv2.putText(frame, f"Current: {self.current_emotion}", 
                  (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)

        # Only update if we have enough samples and high confidence (80%)
        if len(self.emotion_window) >= 5 and max_confidence > 0.5:
            # Get most common emotion in window
            dominant_emotion = Counter(self.emotion_window).most_common(1)[0][0]
            
            if dominant_emotion != self.last_detected_emotion:
                if send_emotion_update(dominant_emotion, max_confidence):
                    if self.pause_mode:
                        # In pause mode, just update emotion and close
                        self.last_detected_emotion = dominant_emotion
                        self.stop_scanning()
                        return
                    elif not is_playing():
                        if start_emotion_playlist(dominant_emotion):
                            self.last_detected_emotion = dominant_emotion
                            self.stop_scanning()
                            return

        cv2.imshow('Emotion Detection', frame)

    def check_pause_and_detect(self):
        """Check if playback is paused and start detection if needed"""
        if not self.scanning and time.time() - self.last_playback_check > self.pause_detection_interval:
            self.last_playback_check = time.time()
            try:
                current_playback = sp.current_playback()
                if current_playback and not current_playback['is_playing']:
                    print("Playback paused - starting emotion detection")
                    self.start_scanning()
            except Exception as e:
                print(f"Error checking playback state: {e}")

def send_emotion_update(emotion_num, confidence):
    """Send emotion to Flask server"""
    try:
        response = requests.post(
            'http://localhost:5000/update-emotion',
            json={
                'emotion': emotion_num,
                'confidence': min(confidence, 0.99)
            },
            timeout=2
        )
        return response.status_code == 200
    except Exception as e:
        print(f"Update error: {str(e)}")
        return False

def get_active_device():
    """Get first active Spotify device"""
    try:
        devices = sp.devices()
        return devices['devices'][0]['id'] if devices['devices'] else None
    except:
        return None

def is_playing():
    """Check if music is currently playing"""
    try:
        playback = sp.current_playback()
        return playback and playback['is_playing']
    except:
        return False

def start_emotion_playlist(emotion_num):
    """Start playback for detected emotion"""
    device_id = get_active_device()
    if device_id and emotion_num in PLAYLIST_MAP:
        try:
            sp.start_playback(
                device_id=device_id,
                context_uri=PLAYLIST_MAP[emotion_num]
            )
            return True
        except Exception as e:
            print(f"Playback error: {str(e)}")
    return False

def pause_and_detect(detector):
    """Handle the pause-and-detect mode functionality"""
    if not detector.scanning:
        if detector.start_scanning(pause_mode=True):
            while True:
                if detector.scanning:
                    detector.detect_emotion()
                
                # Exit conditions:
                # 1. User pressed 'q'
                # 2. Detection completed and scanning stopped
                if cv2.waitKey(1) & 0xFF == ord('q') or not detector.scanning:
                    if detector.scanning:
                        detector.stop_scanning()
                    break
    return detector.last_detected_emotion

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--pause-mode', action='store_true',
                      help='Run in pause-and-detect mode')
    args = parser.parse_args()
    
    detector = EmotionDetector()
    print("Starting emotion detection...")
    
    if args.pause_mode:
        # Run in pause-and-detect mode
        detected_emotion = pause_and_detect(detector)
        if detected_emotion:
            print(f"Detected emotion: {detected_emotion}")
        else:
            print("No emotion detected or detection was cancelled")
    else:
        # Original normal mode operation
        if detector.start_scanning(pause_mode=False):
            while True:
                if detector.scanning:
                    detector.detect_emotion()
                else:
                    # Check if playback is paused and we should detect again
                    detector.check_pause_and_detect()
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    if detector.scanning:
                        detector.stop_scanning()
                    break

    print("Program ended")