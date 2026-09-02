import requests

API_KEY = "pJKJSbWPzCdfm6QMPGDIv6ED2VPOd3ST"

url = "https://api.mistral.ai/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

data = {
    "model": "mistral-small-latest",
    "messages": [
        {"role": "user", "content": "Hola"}
    ]
}

response = requests.post(url, headers=headers, json=data)

print(response.status_code)
print(response.text)