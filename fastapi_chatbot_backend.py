from fastapi import FastAPI, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import shutil
import json
import re
import difflib

from dotenv import load_dotenv
from vision_api.llama_vision import query_vision_llm
from geo_api.ocr_utils import extract_text_from_image, extract_address_from_text, extract_building_info
from geo_api.osm_helper import geocode_address, get_nearby_places
from geo_api.route_api import get_osm_route
from geo_api.accessibility_helper import get_accessibility_info

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
    "building_number": "",
    "location": None,
    "nearby": []
}

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    path = "data/uploaded_map.png"
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    session_state["image_path"] = path
    ocr_text = extract_text_from_image(path)
    print("[DEBUG] Raw OCR text:\n", ocr_text)

    address = extract_address_from_text(ocr_text)
    if not address:
        return JSONResponse(status_code=400, content={"error": "Address not found in image."})
    session_state["address"] = address

    building_name, building_number = extract_building_info(ocr_text)
    if building_number:
        session_state["building_number"] = building_number.strip()

    if not building_name or len(building_name) < 5 or not any(c.isalpha() for c in building_name):
        fallback_prompt = """
        You are a helpful assistant. From this map screenshot popup, extract:
        - Building Name
        - Building Number

        Format your response exactly as:
        Name: <building name>
        Number: <building number>
        """
        try:
            fallback_result = query_vision_llm(path, fallback_prompt)
            print("[LLM Fallback] Response:\n", fallback_result)

            match_name = re.search(r"Name:\s*(.+)", fallback_result)
            match_number = re.search(r"Number:\s*(\d+)", fallback_result)

            if match_name:
                session_state["building_name"] = match_name.group(1).strip()
            if match_number:
                session_state["building_number"] = match_number.group(1).strip()
        except Exception as e:
            print("[ERROR] Fallback LLM failed:", e)
            session_state["building_name"] = "Unknown"
    else:
        session_state["building_name"] = building_name

    if not session_state["building_number"]:
        session_state["building_number"] = "N/A"

    location = geocode_address(address)
    if not location:
        return JSONResponse(status_code=400, content={"error": "Failed to geocode address."})

    session_state["location"] = location
    nearby = get_nearby_places(location["lat"], location["lon"])
    session_state["nearby"] = nearby

    return {
        "building_name": session_state["building_name"],
        "building_number": session_state["building_number"],
        "address": session_state["address"],
        "nearby": nearby
    }

@app.get("/nearby")
async def get_nearby():
    return {"nearby": session_state["nearby"]}

@app.post("/directions")
async def directions(request: Request):
    body = await request.json()
    building_name = body.get("building_name")
    accessibility_enabled = body.get("accessibility", False)

    matched = max(
        session_state["nearby"],
        key=lambda b: difflib.SequenceMatcher(None, b["name"].lower(), building_name.lower()).ratio(),
        default=None
    )
    if not matched:
        return {"directions": [], "llm_response": f"Could not find {building_name} in nearby buildings."}

    directions = get_osm_route(session_state["location"], {"lat": matched["lat"], "lon": matched["lon"]})
    directions = [step for step in directions if not step.startswith("[")]

    accessibility_info = {}
    if accessibility_enabled:
        print("[DEBUG] Fetching accessibility info for:", matched["name"])
        accessibility_info = get_accessibility_info(matched["name"])
        print("[DEBUG] Accessibility fetched:", accessibility_info)

    if directions:
        return {
            "directions": directions,
            "llm_response": "",
            "accessibility": accessibility_info
        }
    else:
        prompt = f"""
        You are a helpful assistant.
        The user is currently at: {session_state['building_name']} (Building {session_state['building_number']}), {session_state['address']}.
        They are trying to reach: {matched['name']} nearby.

        Since routing data is unavailable, try to provide visual navigation help by describing:
        - What’s nearby or between the two buildings
        - What’s on the left, right, or opposite if visible in the image
        - General navigation assistance if possible
        Only respond with the step-by-step navigation instructions starting from the heading 'Navigate to...'. Omit introductions or summaries.
        """
        llm_response = query_vision_llm(session_state["image_path"], prompt)

        lines = llm_response.strip().splitlines()
        trimmed = "\n".join([line for line in lines if line.strip()])
        return {
            "directions": [],
            "llm_response": trimmed,
            "accessibility": accessibility_info
        }
