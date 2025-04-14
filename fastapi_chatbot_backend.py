from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import shutil
import json
import re

from dotenv import load_dotenv
from vision_api.llama_vision import query_vision_llm
from geo_api.ocr_utils import extract_text_from_image, extract_address_from_text
from geo_api.osm_helper import geocode_address, get_nearby_places
from geo_api.route_api import get_osm_route

load_dotenv()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

session_state = {
    "image_path": "",
    "address": "",
    "building_name": "",
    "location": None,
    "nearby": []
}

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    path = f"data/uploaded_map.png"
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    session_state["image_path"] = path

    ocr_text = extract_text_from_image(path)
    address = extract_address_from_text(ocr_text)
    if not address:
        return JSONResponse(status_code=400, content={"error": "Address not found in image."})

    session_state["address"] = address

    lines = ocr_text.splitlines()
    session_state["building_name"] = "Unknown Building"
    for i, line in enumerate(lines):
        if address in line and i > 0:
            session_state["building_name"] = lines[i - 1].strip()
            break

    location = geocode_address(address)
    if not location:
        return JSONResponse(status_code=400, content={"error": "Failed to geocode address."})

    session_state["location"] = location
    nearby = get_nearby_places(location["lat"], location["lon"])
    session_state["nearby"] = nearby

    return {
        "building_name": session_state["building_name"],
        "address": session_state["address"],
        "nearby": nearby
    }

@app.post("/directions")
async def directions(request: Request):
    body = await request.body()
    data = json.loads(body)
    building_name = data.get("building_name")

    matched = next((b for b in session_state["nearby"] if building_name.lower() in b["name"].lower()), None)
    if not matched:
        return {"directions": [], "llm_response": f"Could not find {building_name} in nearby buildings."}

    directions = get_osm_route(session_state["location"], {"lat": matched["lat"], "lon": matched["lon"]})
    directions = [step for step in directions if not step.startswith("[")]

    if directions:
        return {"directions": directions, "llm_response": ""}
    else:
        prompt = f"""
        You are a helpful assistant.
        The user is currently at: {session_state['building_name']}, {session_state['address']}.
        They are trying to reach: {matched['name']} nearby.

        Since routing data is unavailable, try to provide visual navigation help by describing:
        - What’s nearby or between the two buildings
        - What’s on the left, right, or opposite if visible in the image
        - General navigation assistance if possible
        Only respond with the step-by-step navigation instructions starting from the heading 'Navigate to...'. Omit introductions or summaries.
        """
        llm_response = query_vision_llm(session_state["image_path"], prompt)

        # Trim empty lines from the final output
        lines = llm_response.strip().splitlines()
        trimmed = "\n".join([line for line in lines if line.strip()])
        return {"directions": [], "llm_response": trimmed}
