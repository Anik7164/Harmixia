import cv2
import time
from collections import Counter
from deepface import DeepFace
from spotify_auth import sp  

face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

emotion_playlist = {
    "happy": "spotify:playlist:0aX9sMCpue9ZFnKcoErL7d",
    "sad": "spotify:playlist:37i9dQZF1DX3YSRoSdA634",
    "angry": "spotify:playlist:1mulv2QJmZQZik4tYR8V0j",
    "neutral": "spotify:playlist:1mulv2QJmZQZik4tYR8V0j"
}

def get_active_device():
    devices = sp.devices()
    if devices['devices']:
        return devices['devices'][0]['id']  
    else:
        print("No active Spotify device found. Open Spotify and play a song manually first.")
        return None

def is_song_playing():
    try:
        playback = sp.current_playback()
        return playback and playback['is_playing']
    except:
        return False

while True:
    if is_song_playing():
        time.sleep(5)  # Check every 5 seconds while the song is playing
        continue
    
    cap = cv2.VideoCapture(0)
    last_detected_emotion = None  # Last detected emotion
    detected_emotions = []  # Recent emotions storage
    cooldown_time = time.time()  # Timer for detection
    
    while True:
        if is_song_playing():
            cap.release()
            cv2.destroyAllWindows()
            break  # Stop scanning when music starts
        
        ret, frame = cap.read()
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        rgb_frame = cv2.cvtColor(gray_frame, cv2.COLOR_GRAY2RGB)

        # Detect faces
        faces = face_cascade.detectMultiScale(gray_frame, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        emotions_in_frame = []  # Collect emotions detected in the frame

        for (x, y, w, h) in faces:
            face_roi = rgb_frame[y:y + h, x:x + w]
            result = DeepFace.analyze(face_roi, actions=['emotion'], enforce_detection=False)
            emotion = result[0]['dominant_emotion']
            emotions_in_frame.append(emotion)

            # Draw face rectangle and label
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
            cv2.putText(frame, emotion, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
        
        # Store emotions in the last 5 seconds
        if emotions_in_frame:
            detected_emotions.extend(emotions_in_frame)
            if len(detected_emotions) > 6:
                detected_emotions.pop(0)
        
        # Process emotion change every 5 seconds
        if time.time() - cooldown_time > 6 and detected_emotions:
            most_common_emotion = Counter(detected_emotions).most_common(1)[0][0]  # Get the most frequent emotion
            detected_emotions = []  # Reset detected emotions
            cooldown_time = time.time()  # Reset timer

            # Check if emotion has changed before updating playlist
            if most_common_emotion != last_detected_emotion:
                last_detected_emotion = most_common_emotion
                if most_common_emotion in emotion_playlist:
                    device_id = get_active_device()
                    if device_id:
                        print(f"Playing playlist for emotion: {most_common_emotion}")
                        sp.start_playback(device_id=device_id, context_uri=emotion_playlist[most_common_emotion])
                        cap.release()
                        cv2.destroyAllWindows()
                        break  # Stop scanning when music starts

        cv2.imshow('Real-time Emotion Detection', frame)

        # Exit condition
        if cv2.waitKey(1) & 0xFF == ord('s'):
            cap.release()
            cv2.destroyAllWindows()
            exit()
    
    while is_song_playing():
        time.sleep(1)  # Wait for song to finish before restarting camera
