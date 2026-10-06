import json
import urllib.request
import sys

BASE_URL = "https://echoinsight-ouvp.onrender.com/api/v1"
CONV_ID = "0b0387ee"

def main():
    print(f"Logging in as admin to get token...")
    # 1. Login to get token
    req = urllib.request.Request(
        f"{BASE_URL}/auth/login",
        data=b'{"username":"admin","password":"admin123"}',
        headers={'Content-Type': 'application/json'}
    )
    
    try:
        resp = urllib.request.urlopen(req)
        token = json.loads(resp.read())["access_token"]
        print(f"Success! Got token: {token[:15]}...\n")
    except Exception as e:
        print(f"Login failed: {e}")
        sys.exit(1)

    # 2. Connect to the stream
    stream_url = f"{BASE_URL}/conversations/{CONV_ID}/stream"
    print(f"Connecting to {stream_url} ...")
    stream_req = urllib.request.Request(
        stream_url,
        headers={'Authorization': f'Bearer {token}'}
    )
    
    try:
        with urllib.request.urlopen(stream_req) as response:
            print("Connected! Listening for events (Press Ctrl+C to stop):\n")
            # Read the stream line by line
            for line in response:
                decoded = line.decode('utf-8').strip()
                if decoded:
                    print(decoded)
    except urllib.error.HTTPError as e:
        print(f"Failed to connect to stream: HTTP {e.code} - {e.reason}")
    except KeyboardInterrupt:
        print("\nStopped.")

if __name__ == "__main__":
    main()
