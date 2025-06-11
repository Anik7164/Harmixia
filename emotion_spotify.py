import cv2
import time
import requests
from collections import Counter
from deepface import DeepFace
from spotify_auth import sp  


face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')


EMOTION_MAP = {
    "happy": 2,
    "sad": 3,
    "angry": 4,
    "neutral": 5,
    "nothing": 1  
}


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

def send_emotion_update(emotion_num, confidence):
    """Send emotion to Flask server to update CSS theme"""
    try:
        response = requests.post(
            'http://localhost:5000/update-emotion',
            json={
                'emotion': emotion_num,
                'confidence': min(confidence, 0.5)
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

def is_song_playing():
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

while True:
    if is_song_playing():
        time.sleep(5)  
        continue
    
    cap = cv2.VideoCapture(0)
    last_detected_emotion = None  
    detected_emotions = []  
    cooldown_time = time.time()  
    
    while True:
        if is_song_playing():
            cap.release()
            cv2.destroyAllWindows()
            break  
        
        ret, frame = cap.read()
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        faces = face_cascade.detectMultiScale(gray_frame, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        emotions_in_frame = []  
        max_confidence = 0

        for (x, y, w, h) in faces:
            face_roi = rgb_frame[y:y + h, x:x + w]
            result = DeepFace.analyze(face_roi, actions=['emotion'], enforce_detection=False)
            emotion = result[0]['dominant_emotion']
            confidence = result[0]['emotion'][emotion]/100
            emotions_in_frame.append(emotion)
            
            if confidence > max_confidence:
                max_confidence = confidence

            # Get color for detected emotion
            color = EMOTION_COLORS.get(emotion, (128, 128, 128))
            
            # Draw visualization with emotion-specific color
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            cv2.putText(frame, f"{emotion} ({confidence:.0%})", 
                      (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
        
        # Display current emotion status
        current_status = "No face detected" if not emotions_in_frame else f"Current: {emotions_in_frame[-1]}"
        status_color = EMOTION_COLORS.get(emotions_in_frame[-1] if emotions_in_frame else "nothing", (128, 128, 128))
        cv2.putText(frame, current_status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
        
        if emotions_in_frame:
            detected_emotions.extend(emotions_in_frame)
            if len(detected_emotions) > 6:
                detected_emotions.pop(0)
        
        if time.time() - cooldown_time > 6 and detected_emotions:
            most_common_emotion = Counter(detected_emotions).most_common(1)[0][0]  
            emotion_num = EMOTION_MAP.get(most_common_emotion, 1)
            detected_emotions = []  
            cooldown_time = time.time()  

            if emotion_num != last_detected_emotion:
                # Update web interface with new emotion
                if send_emotion_update(emotion_num, max_confidence):
                    last_detected_emotion = emotion_num
                    # Start corresponding playlist if music isn't playing
                    if not is_song_playing():
                        if start_emotion_playlist(emotion_num):
                            cap.release()
                            cv2.destroyAllWindows()
                            break

        cv2.imshow('Real-time Emotion Detection', frame)

        if cv2.waitKey(1) & 0xFF == ord('s'):
            cap.release()
            cv2.destroyAllWindows()
            exit()
    
    while is_song_playing():
        time.sleep(1)