import cv2
import time
from deepface import DeepFace
from spotify_auth import sp  # Import Spotify authentication

# Load OpenCV face detection model
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# Emotion to Spotify playlist mapping
emotion_playlist = {
    "happy": "spotify:playlist:37i9dQZF1DXdPec7aLTmlC",
    "sad": "spotify:playlist:37i9dQZF1DX3YSRoSdA634",
    "angry": "spotify:playlist:37i9dQZF1DX0KpeLFwA3tO",
    "neutral": "spotify:playlist:37i9dQZF1DWZqd5JICZI0u"
}

# Function to get active Spotify device ID
def get_active_device():
    devices = sp.devices()
    if devices['devices']:
        return devices['devices'][0]['id']  # Use the first active device
    else:
        print("No active Spotify device found. Open Spotify and play a song manually first.")
        return None

# Function to check if the song is still playing
def is_song_playing():
    try:
        playback = sp.current_playback()
        return playback and playback['is_playing']
    except:
        return False

# Start capturing video
cap = cv2.VideoCapture(0)

last_detected_emotion = None  # Store last detected emotion

while True:
    ret, frame = cap.read()
    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    rgb_frame = cv2.cvtColor(gray_frame, cv2.COLOR_GRAY2RGB)

    # Detect faces in the frame
    faces = face_cascade.detectMultiScale(gray_frame, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

    for (x, y, w, h) in faces:
        face_roi = rgb_frame[y:y + h, x:x + w]

        # Perform emotion analysis
        result = DeepFace.analyze(face_roi, actions=['emotion'], enforce_detection=False)
        emotion = result[0]['dominant_emotion']

        # If the detected emotion is the same as last one, do nothing
        if emotion == last_detected_emotion and is_song_playing():
            continue  # Skip detection and let the song play

        # Update last detected emotion
        last_detected_emotion = emotion

        # Draw rectangle and display emotion on frame
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
        cv2.putText(frame, emotion, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)

        # Play the corresponding playlist if emotion is detected
        if emotion in emotion_playlist:
            device_id = get_active_device()
            if device_id:
                print(f"Playing playlist for emotion: {emotion}")
                sp.start_playback(device_id=device_id, context_uri=emotion_playlist[emotion])

    # Display the output
    cv2.imshow('Real-time Emotion Detection', frame)

    # Wait for song to finish before detecting again
    while is_song_playing():
        time.sleep(5)  # Check every 5 seconds

    # Exit on pressing 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
