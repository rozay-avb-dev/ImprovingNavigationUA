import cv2
import pytesseract
from PIL import Image
import os
import re

pytesseract.pytesseract.tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"  # adjust if needed

def preprocess_image_for_ocr(image_path):
    image = cv2.imread(image_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    scale_percent = 200
    width = int(gray.shape[1] * scale_percent / 100)
    height = int(gray.shape[0] * scale_percent / 100)
    resized = cv2.resize(gray, (width, height), interpolation=cv2.INTER_LINEAR)
    thresh = cv2.adaptiveThreshold(resized, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 15, 9)
    return thresh

def extract_text_from_image(image_path: str) -> str:
    try:
        processed_image = preprocess_image_for_ocr(image_path)
        raw_text = pytesseract.image_to_string(processed_image)
        utf8_text = raw_text.encode('utf-8', errors='ignore').decode('utf-8')
        return utf8_text.strip()
    except Exception as e:
        print("[ERROR] OCR failed:", e)
        return ""

def extract_address_from_text(text: str) -> str:
    match = re.search(r'\d{3,5}\s+[A-Z][a-zA-Z]*\s+(University|Main|Park|Cherry|6th|1st|2nd|Street|Avenue|Blvd)[^\n,]*', text)
    if match:
        return match.group(0).strip()
    return None

def extract_building_info(text: str):
    lines = text.splitlines()
    name_candidate = ""
    number_candidate = ""

    for i, line in enumerate(lines):
        if "building number" in line.lower():
            match = re.search(r"\d{1,4}", line)
            if match:
                number_candidate = match.group()
        if re.search(r"\d{3,5}\s+E University Blvd", line):
            if i > 0 and len(lines[i - 1].strip()) > 3:
                name_candidate = lines[i - 1].strip()

    return name_candidate.strip(), number_candidate.strip()
