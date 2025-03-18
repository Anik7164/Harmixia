from flask import Flask, jsonify
import subprocess

app = Flask(__name__)

@app.route('/run-emotion-spotify', methods=['GET'])
def run_emotion_spotify():
    try:
        # Run emotion_spotify.py and capture its output
        result = subprocess.run(["python", "emotion_spotify.py"], capture_output=True, text=True)
        return jsonify({"output": result.stdout, "error": result.stderr})
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(debug=True)
