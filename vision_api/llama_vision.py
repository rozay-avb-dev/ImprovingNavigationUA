import base64
import os
import requests

def encode_image_to_base64(image_path):
    with open(image_path, "rb") as f:
        return f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"

def query_vision_llm(image_path, user_prompt):
    url = os.environ["LLM_BASE"] + "/v1/chat/completions"
    token = os.environ["OPENAI_API_KEY"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    image_b64 = encode_image_to_base64(image_path)

    payload = {
        "model": "Llama-3.2-11B-Vision-Instruct",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant that analyzes campus maps."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": image_b64}}
                ]
            }
        ],
        "temperature": 0.2
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        print("[ERROR] LLM API returned:", response.status_code)
        print("[DEBUG] Response text:", response.text)
        return "Sorry, I couldn't generate a description due to an API issue."

    try:
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        print("[ERROR] Failed to parse LLM JSON:", e)
        print("[DEBUG] Response content:", response.content)
        return "Sorry, the LLM response couldn't be processed."
