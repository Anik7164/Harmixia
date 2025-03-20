import os
import subprocess
from flask import Flask, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Get the full absolute path to emotion_spotify.py
script_path = os.path.abspath("C:/xampp/htdocs/Harmixia/emotion_spotify.py")

@app.route('/start-scanning', methods=['POST'])
def start_scanning():
    try:
        if not os.path.exists(script_path):  # Check if the file actually exists
            return f"Error: File not found at {script_path}", 500
        
        process = subprocess.Popen(['python', script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()

        if stderr:
            return f"Error: {stderr.decode('utf-8')}", 500
        
        return "Face scanning started!", 200
    except Exception as e:
        return f"Exception: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
