import os
import base64
import pytesseract
from PIL import Image
import io

TOOL_NAME = "ocr"
TOOL_DESCRIPTION = "Extract text from an image file or from the current screen (full, left half, or right half)"
TOOL_ARGS = {"source": "str: 'screen', 'screen_left', 'screen_right', or a file path to an image"}

def _crop_half(img, side):
    width, height = img.size
    if side == "left":
        return img.crop((0, 0, width // 2, height))
    elif side == "right":
        return img.crop((width // 2, 0, width, height))
    return img

def _preprocess(img):
    # convert to grayscale
    img = img.convert("L")
    # upscale 2x for better OCR on small UI text
    width, height = img.size
    img = img.resize((width * 2, height * 2), Image.LANCZOS)
    return img

def run(args=None):
    source = args.get("source", "screen") if args else "screen"

    try:
        if source.startswith("screen"):
            from tools.sidecar import screenshot
            result = screenshot()
            image_b64 = result.get("image", "")
            if not image_b64:
                return {"error": "no screenshot available"}
            image_data = base64.b64decode(image_b64)
            img = Image.open(io.BytesIO(image_data))

            if source == "screen_left":
                img = _crop_half(img, "left")
            elif source == "screen_right":
                img = _crop_half(img, "right")
        else:
            path = os.path.expanduser(source)
            if not os.path.exists(path):
                return {"error": f"file not found: {path}"}
            img = Image.open(path)

        img = _preprocess(img)
        text = pytesseract.image_to_string(img, config="--psm 6")
        text = text.strip()

        if not text:
            return {"status": "ok", "result": "No readable text found in the image."}

        return {"status": "ok", "result": text[:2000]}

    except Exception as e:
        return {"error": str(e)}
