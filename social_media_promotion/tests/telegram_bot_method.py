import os
import requests
import json
import ffmpeg
from PIL import Image, ImageFilter

# ===============================
# CONFIG - Fill in your 4 details
# ===============================
# 1. Your bot's token from @BotFather
BOT_TOKEN = "7961690843:AAEeBijvnf5Br_-yAbWrCH2HF5OKLMT1CMA"

# 2. The numerical ID of your channel
CHAT_ID = -1002997522860

# 3. Your Business Connection ID for posting stories as yourself
BUSINESS_CONNECTION_ID = "1KHuGqUq-VWBAgAAuhG8ad-b-PA" # Make sure this is a fresh ID

# 4. The path to your FFmpeg 'bin' folder (use r"..." for Windows paths)
FFMPEG_PATH = r"F:\ffmpeg\ffmpeg-master-latest-win64-gpl-shared\bin"

# --- Leave this as is ---
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ===============================
# MEDIA PROCESSING HELPERS
# ===============================

def fit_image_for_story(image_path, output_path, target_size=(1080, 1920)):
    """Fits the entire image within the frame, adding a blurred background."""
    img = Image.open(image_path).convert("RGB")
    img.thumbnail(target_size, Image.Resampling.LANCZOS)
    background = Image.open(image_path).convert("RGB")
    background = background.resize(target_size, Image.Resampling.LANCZOS)
    background = background.filter(ImageFilter.GaussianBlur(radius=30))
    paste_x = (target_size[0] - img.width) // 2
    paste_y = (target_size[1] - img.height) // 2
    background.paste(img, (paste_x, paste_y))
    background.save(output_path, "JPEG", quality=95)

def process_video_for_story(input_path, output_path, target_size=(720, 1280)):
    """Fits a video into the target frame and reliably preserves the audio."""
    ffmpeg_cmd = os.path.join(FFMPEG_PATH, 'ffmpeg.exe') if FFMPEG_PATH else 'ffmpeg'
    ffprobe_cmd = os.path.join(FFMPEG_PATH, 'ffprobe.exe') if FFMPEG_PATH else 'ffprobe'
    try:
        print("Probing video file...")
        probe = ffmpeg.probe(input_path, cmd=ffprobe_cmd)
        has_audio = any(s['codec_type'] == 'audio' for s in probe['streams'])
        print("Processing video with FFmpeg...")
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
            print("Audio stream found. Copying it directly.")
            audio_stream = input_stream['a:0']
            final_streams.append(audio_stream)
            output_params['acodec'] = 'copy'
        else:
            print("No audio stream found.")
        (
            ffmpeg.output(*final_streams, output_path, **output_params)
            .overwrite_output()
            .run(quiet=True, cmd=ffmpeg_cmd)
        )
        print("Video processing complete.")
        return True
    except Exception as e:
        print(f"An error occurred during video processing with FFmpeg: {e}")
        return False

# ====================================================
# SECTION 1: FUNCTIONS FOR YOUR CHANNEL
# ====================================================

def send_text_to_channel(text: str):
    """Sends a plain text message to the channel specified in CHAT_ID."""
    print(f"Sending text to channel {CHAT_ID}...")
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    r = requests.post(url, json=payload)
    return r.json()

def send_photo_to_channel(image_file, caption=None):
    """Sends a photo to the channel specified in CHAT_ID."""
    print(f"Sending photo to channel {CHAT_ID}...")
    url = f"{BASE_URL}/sendPhoto"
    data = {"chat_id": CHAT_ID}
    if caption: data["caption"] = caption
    with open(image_file, "rb") as f:
        files = {"photo": f}
        r = requests.post(url, data=data, files=files)
    return r.json()

def send_video_to_channel(video_file, caption=None):
    """Sends a video to the channel specified in CHAT_ID."""
    print(f"Sending video to channel {CHAT_ID}...")
    url = f"{BASE_URL}/sendVideo"
    data = {"chat_id": CHAT_ID}
    if caption: data["caption"] = caption
    with open(video_file, "rb") as f:
        files = {"video": f}
        r = requests.post(url, data=data, files=files)
    return r.json()

# =============================================================
# SECTION 2: FUNCTIONS FOR YOUR PERSONAL ACCOUNT STORY
# =============================================================

def post_photo_story_as_user(image_file, caption=None, active_period=86400):
    """Processes and posts a photo story to your PERSONAL ACCOUNT."""
    if not BUSINESS_CONNECTION_ID: raise ValueError("Business Connection ID is required.")
    print("Processing and posting photo story as user...")
    processed_image_path = f"processed_story_{os.getpid()}.jpg"
    try:
        fit_image_for_story(image_file, processed_image_path)
        url = f"{BASE_URL}/postStory"
        attach_name = "story_photo"
        content = {"type": "photo", "photo": f"attach://{attach_name}"}
        data = { "business_connection_id": BUSINESS_CONNECTION_ID, "content": json.dumps(content), "active_period": active_period }
        if caption: data["caption"] = caption
        with open(processed_image_path, "rb") as f:
            files = {attach_name: f}
            r = requests.post(url, data=data, files=files)
        return r.json()
    finally:
        if os.path.exists(processed_image_path):
            os.remove(processed_image_path)

def post_video_story_as_user(video_file, caption=None, active_period=86400):
    """Processes and posts a video story to your PERSONAL ACCOUNT."""
    if not BUSINESS_CONNECTION_ID: raise ValueError("Business Connection ID is required.")
    print("Processing and posting video story as user...")
    processed_video_path = f"processed_story_{os.getpid()}.mp4"
    try:
        success = process_video_for_story(video_file, processed_video_path)
        if not success:
            return {"ok": False, "description": "Video processing failed. Check FFmpeg installation and path."}
        url = f"{BASE_URL}/postStory"
        attach_name = "story_video"
        content = {"type": "video", "video": f"attach://{attach_name}"}
        data = { "business_connection_id": BUSINESS_CONNECTION_ID, "content": json.dumps(content), "active_period": active_period }
        if caption: data["caption"] = caption
        with open(processed_video_path, "rb") as f:
            files = {attach_name: f}
            r = requests.post(url, data=data, files=files)
        return r.json()
    finally:
        if os.path.exists(processed_video_path):
            os.remove(processed_video_path)

if __name__ == "__main__":
    # === To post to your CHANNEL, uncomment one of these ===
    #print(send_text_to_channel("Hello from my bot!"))
    #print(send_photo_to_channel("./example.png", caption="A photo for our channel."))
    #print(send_video_to_channel("./televideos/join_my_channel.mp4", caption="A video for our channel."))

    # === To post a STORY to your PERSONAL ACCOUNT, uncomment one of these ===
    #print(post_photo_story_as_user("./example.png", caption="A perfectly fitted photo story!"))
    #print(post_video_story_as_user("./televideos/join_my_channel.mp4", caption="Join us @artpmtns!"))
    
    print("\nScript finished.")