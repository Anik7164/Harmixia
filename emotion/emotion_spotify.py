import cv2
import time
from collections import Counter
from deepface import DeepFace
from spotify_auth import sp  


face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')


emotion_playlist = {
    "happy": "spotify:playlist:37i9dQZF1DXdPec7aLTmlC",
    "sad": "spotify:playlist:37i9dQZF1DX3YSRoSdA634",
    "angry": "spotify:playlist:37i9dQZF1DX0KpeLFwA3tO",
    "neutral": "spotify:playlist:37i9dQZF1DWZqd5JICZI0u"
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

# Start capturing video
cap = cv2.VideoCapture(0)

last_detected_emotion = None  # last detect
detected_emotions = []  #recent
cooldown_time = time.time()  # Timer detect

while True:
    ret, frame = cap.read()
    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    rgb_frame = cv2.cvtColor(gray_frame, cv2.COLOR_GRAY2RGB)

    # frame
    faces = face_cascade.detectMultiScale(gray_frame, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

    emotions_in_frame = []  # Collect

    for (x, y, w, h) in faces:
        face_roi = rgb_frame[y:y + h, x:x + w]

        result = DeepFace.analyze(face_roi, actions=['emotion'], enforce_detection=False)
        emotion = result[0]['dominant_emotion']
        emotions_in_frame.append(emotion)

    
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
        cv2.putText(frame, emotion, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)

    
    if emotions_in_frame:
        detected_emotions.extend(emotions_in_frame)
        if len(detected_emotions) > 10:  #last 10 sec
            detected_emotions.pop(0)

    # new in 10 seconds
    if time.time() - cooldown_time > 10 and detected_emotions:
        most_common_emotion = Counter(detected_emotions).most_common(1)[0][0]  # Get the most frequent emotion
        detected_emotions = []  # Reset
        cooldown_time = time.time()  # Reset timer

        if most_common_emotion == last_detected_emotion and is_song_playing():
            continue

        last_detected_emotion = most_common_emotion

        if most_common_emotion in emotion_playlist:
            device_id = get_active_device()
            if device_id:
                print(f"Playing playlist for emotion: {most_common_emotion}")
                sp.start_playback(device_id=device_id, context_uri=emotion_playlist[most_common_emotion])


    cv2.imshow('Real-time Emotion Detection', frame)

    # Exit on pressing 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()