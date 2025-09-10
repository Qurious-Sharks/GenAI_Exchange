import os
import requests
import json
import ffmpeg
from PIL import Image, ImageFilter
from dotenv import load_dotenv
from crewai.tools import tool

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
BUSINESS_CONNECTION_ID = os.getenv("BUSINESS_CONNECTION_ID")
FFMPEG_PATH = r"F:\ffmpeg\ffmpeg-master-latest-win64-gpl-shared\bin"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def _fit_image_for_story(image_path, output_path, target_size=(1080, 1920)):
    """Internal helper to fit an image to story dimensions."""
    img = Image.open(image_path).convert("RGB")
    img.thumbnail(target_size, Image.Resampling.LANCZOS)
    background = Image.open(image_path).convert("RGB")
    background = background.resize(target_size, Image.Resampling.LANCZOS)
    background = background.filter(ImageFilter.GaussianBlur(radius=30))
    paste_x = (target_size[0] - img.width) // 2
    paste_y = (target_size[1] - img.height) // 2
    background.paste(img, (paste_x, paste_y))
    background.save(output_path, "JPEG", quality=95)

def _process_video_for_story(input_path, output_path, target_size=(720, 1280)):
    """Internal helper to fit a video to story dimensions."""
    ffmpeg_cmd = os.path.join(FFMPEG_PATH, 'ffmpeg.exe') if FFMPEG_PATH else 'ffmpeg'
    ffprobe_cmd = os.path.join(FFMPEG_PATH, 'ffprobe.exe') if FFMPEG_PATH else 'ffprobe'
    try:
        probe = ffmpeg.probe(input_path, cmd=ffprobe_cmd)
        has_audio = any(s['codec_type'] == 'audio' for s in probe['streams'])
        input_stream = ffmpeg.input(input_path)
        video_stream = (
            input_stream['v:0']
            .filter('scale', target_size[0], target_size[1], force_original_aspect_ratio='decrease')
            .filter('pad', target_size[0], target_size[1], '(ow-iw)/2', '(oh-ih)/2', 'black')
        )
        output_params = {
            'vcodec': 'libx265', 'pix_fmt': 'yuv420p',
            'crf': 28, 'preset': 'fast', 'movflags': '+faststart'
        }
        final_streams = [video_stream]
        if has_audio:
            audio_stream = input_stream['a:0']
            final_streams.append(audio_stream)
            output_params['acodec'] = 'copy'
        
        (
            ffmpeg.output(*final_streams, output_path, **output_params)
            .overwrite_output()
            .run(quiet=True, cmd=ffmpeg_cmd)
        )
        return True
    except Exception as e:
        print(f"An error occurred during video processing: {e}")
        return False

# ====================================================
# SECTION 1: TOOLS FOR A TELEGRAM CHANNEL
# ====================================================

@tool("send_text_to_telegram_channel")
def send_text_to_channel(text: str) -> str:
    """Sends a plain text message to the pre-configured Telegram channel."""
    print(f"Sending text to channel {CHAT_ID}...")
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    r = requests.post(url, json=payload)
    return json.dumps(r.json())

@tool("send_photo_to_telegram_channel")
def send_photo_to_channel(image_file: str, caption: str | None = None) -> str:
    """Sends a photo to the pre-configured Telegram channel.
    Args:
        image_file (str): The local file path to the image to send.
        caption (str, optional): A text caption for the photo.
    """
    print(f"Sending photo to channel {CHAT_ID}...")
    url = f"{BASE_URL}/sendPhoto"
    data = {"chat_id": CHAT_ID}
    if caption: data["caption"] = caption
    with open(image_file, "rb") as f:
        files = {"photo": f}
        r = requests.post(url, data=data, files=files)
    return json.dumps(r.json())

@tool("send_video_to_telegram_channel")
def send_video_to_channel(video_file: str, caption: str | None = None) -> str:
    """Sends a video to the pre-configured Telegram channel.
    Args:
        video_file (str): The local file path to the video to send.
        caption (str, optional): A text caption for the video.
    """
    print(f"Sending video to channel {CHAT_ID}...")
    url = f"{BASE_URL}/sendVideo"
    data = {"chat_id": CHAT_ID}
    if caption: data["caption"] = caption
    with open(video_file, "rb") as f:
        files = {"video": f}
        r = requests.post(url, data=data, files=files)
    return json.dumps(r.json())

# =============================================================
# SECTION 2: TOOLS FOR A PERSONAL TELEGRAM ACCOUNT STORY
# =============================================================

@tool("post_photo_story_to_personal_telegram")
def post_photo_story_as_user(image_file: str, caption: str | None = None, active_period: int = 86400) -> str:
    """Processes an image and posts it as a story to the user's personal Telegram account.
    Args:
        image_file (str): The local file path to the image for the story.
        caption (str, optional): A text caption for the story.
        active_period (int, optional): Duration in seconds the story remains active. Defaults to 24 hours (86400).
    """
    if not BUSINESS_CONNECTION_ID: raise ValueError("Business Connection ID is required for posting stories.")
    print("Processing and posting photo story as user...")
    processed_image_path = f"processed_story_{os.getpid()}.jpg"
    try:
        _fit_image_for_story(image_file, processed_image_path)
        url = f"{BASE_URL}/postStory"
        attach_name = "story_photo"
        content = {"type": "photo", "photo": f"attach://{attach_name}"}
        data = { "business_connection_id": BUSINESS_CONNECTION_ID, "content": json.dumps(content), "active_period": active_period }
        if caption: data["caption"] = caption
        with open(processed_image_path, "rb") as f:
            files = {attach_name: f}
            r = requests.post(url, data=data, files=files)
        return json.dumps(r.json())
    finally:
        if os.path.exists(processed_image_path):
            os.remove(processed_image_path)

@tool("post_video_story_to_personal_telegram")
def post_video_story_as_user(video_file: str, caption: str | None = None, active_period: int = 86400) -> str:
    """Processes a video and posts it as a story to the user's personal Telegram account.
    Args:
        video_file (str): The local file path to the video for the story.
        caption (str, optional): A text caption for the story.
        active_period (int, optional): Duration in seconds the story remains active. Defaults to 24 hours (86400).
    """
    if not BUSINESS_CONNECTION_ID: raise ValueError("Business Connection ID is required for posting stories.")
    print("Processing and posting video story as user...")
    processed_video_path = f"processed_story_{os.getpid()}.mp4"
    try:
        if not _process_video_for_story(video_file, processed_video_path):
            return json.dumps({"ok": False, "description": "Video processing failed. Check FFmpeg installation and path."})
        
        url = f"{BASE_URL}/postStory"
        attach_name = "story_video"
        content = {"type": "video", "video": f"attach://{attach_name}"}
        data = { "business_connection_id": BUSINESS_CONNECTION_ID, "content": json.dumps(content), "active_period": active_period }
        if caption: data["caption"] = caption
        with open(processed_video_path, "rb") as f:
            files = {attach_name: f}
            r = requests.post(url, data=data, files=files)
        return json.dumps(r.json())
    finally:
        if os.path.exists(processed_video_path):
            os.remove(processed_video_path)