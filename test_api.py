import requests
import json

BASE_URL = "http://localhost:5000"

    # Note: These URLs might not be valid or might change, they are just for structure testing
    urls = [
        ("https://www.youtube.com/watch?v=aqz-KE-bpKQ", "video"),  # YouTube Video
        ("https://www.youtube.com/watch?v=aqz-KE-bpKQ", "audio"),  # YouTube Audio
        ("https://www.pinterest.com/pin/123456789/", "video"),     # Pinterest
        ("https://x.com/jack/status/20", "video"),                 # X/Twitter
    ]
    
    for url, type_ in urls:
        print(f"Testing URL ({type_}): {url}")
        try:
            response = requests.post(f"{BASE_URL}/download", json={"url": url, "type": type_})
            print(f"Status Code: {response.status_code}")
            print(f"Response: {json.dumps(response.json(), indent=2)}")
        except Exception as e:
            print(f"Error: {e}")
        print("-" * 20)
