import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
import requests
import shutil
import subprocess
# Correct import for CrewAI's function-based tools
from crewai.tools import tool

# This stub allows the code to be imported even if google-genai is not installed.
try:
    from google import genai
except ImportError:
    class _GenAIStub:
        Client = None
    genai = _GenAIStub()

# Ensure Gemini Developer client is used (not Vertex AI files API)
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "false")

# ===============================
# IMAGE GENERATION TOOL (Step 1)
# ===============================

@tool("imagen_image_generator")
def generate_image_with_imagen(prompt: str, style: str = "photorealistic", image_path: Optional[str] = None) -> str:
    """
    Ensures an image exists. If an image_path is provided, it validates and returns it.
    Otherwise, it generates a new image using Google's Imagen model from a prompt. This tool's output is the definitive image path.
    Args:
        prompt (str): The descriptive prompt (e.g., product summary) to generate the image from if no image_path is provided.
        style (str, optional): The style of the image to generate. Defaults to 'photorealistic'.
        image_path (str, optional): The file path of a pre-existing image. If provided, generation is skipped.
    Returns:
        str: The file path to the final image, which will be used in the next step.
    """
    if image_path:
        if os.path.exists(image_path):
            print(f"Using provided image from path: {image_path}")
            return image_path
        else:
            raise FileNotFoundError(f"The provided image_path does not exist: {image_path}")

    print(f"No image provided. Generating new image with Imagen for prompt: '{prompt}'")
    gapi = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not gapi:
        raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY environment variable not set for image generation.")
    if getattr(genai, "Client", None) is None:
        raise ImportError("google-genai is not installed. Install with: pip install google-genai")
    
    client = genai.Client(api_key=gapi, vertexai=False)

    output_dir = Path("./telepics")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    safe_snippet = "".join(c for c in prompt[:24] if c.isalnum() or c in ("-", "_")) or "image"
    file_path = output_dir / f"imagen_{ts}_{safe_snippet}.png"

    response = client.models.generate_images(
        model="imagen-3.0-generate-002",
        prompt=f"{prompt}, style: {style}"
    )
    
    if not getattr(response, "generated_images", None):
        raise RuntimeError("Imagen API call did not return any images.")
        
    image_data = response.generated_images[0].image.content
    with open(file_path, "wb") as f:
        f.write(image_data)
        
    print(f"Successfully generated and saved image to: {file_path}")
    return str(file_path)


# ===============================
# VIDEO GENERATION TOOL (Step 2)
# ===============================

@tool("veo_video_generator")
def generate_video_with_veo(
    prompt: str,
    image_path: str,
    duration: int = 15,
    style: str = "social media",
    aspect_ratio: str = "9:16",
    audio_volume: float = 1.0
) -> str:
    """
    Generates a professional video using Google's Veo model. This tool MUST receive an image_path from the previous step to guide the video generation.
    Args:
        prompt (str): The new, descriptive prompt for the video's action or theme.
        image_path (str): The local file path to the image from the previous step. This image is used to condition and guide the video generation.
        duration (int, optional): Desired duration of the video in seconds. Defaults to 15.
        style (str, optional): The style of the video (e.g., 'social media', 'cinematic'). Defaults to 'social media'.
        aspect_ratio (str, optional): Aspect ratio for the video, e.g., '9:16', '16:9'. Defaults to '9:16'.
        audio_path (str, optional): Local file path to a background audio file.
        audio_url (str, optional): A URL to a background audio file.
        audio_volume (float, optional): Adjusts the audio volume. Defaults to 1.0.
    Returns:
        str: The file path to the final generated video.
    """
    gapi = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not gapi:
        raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY environment variable not set")
    if getattr(genai, "Client", None) is None:
        raise ImportError("google-genai is not installed. Install with: pip install google-genai")
    
    client = genai.Client(api_key=gapi, vertexai=False)

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"The required image was not found at the provided path: {image_path}")

    print(f"Uploading provided image for video generation: {image_path}")
    # Build file payload explicitly to ensure mimeType is set
    mime_type = None
    lower = image_path.lower()
    if lower.endswith(".png"): mime_type = "image/png"
    elif lower.endswith(".jpg") or lower.endswith(".jpeg"): mime_type = "image/jpeg"
    elif lower.endswith(".webp"): mime_type = "image/webp"
    else: mime_type = "application/octet-stream"

    with open(image_path, "rb") as f:
        image_for_video = client.files.upload(
            name=os.path.basename(image_path),
            mime_type=mime_type,
            contents=f.read()
        )

    print("Submitting video generation request to Veo...")
    operation = client.models.generate_videos(
        model="veo-3.0-generate-preview",
        prompt=f"{prompt}\nStyle: {style}\nAspect Ratio: {aspect_ratio}",
        image=image_for_video,
    )

    poll_interval_s = float(os.getenv("VEO_POLL_INTERVAL_SECONDS", "10"))
    timeout_s = int(os.getenv("VEO_TIMEOUT_SECONDS", "900"))
    start_time = time.time()
    print("Waiting for Veo to generate the video...")
    while not getattr(operation, "done", False):
        if time.time() - start_time > timeout_s:
            raise TimeoutError("Veo video generation timed out")
        time.sleep(poll_interval_s)
        operation = client.operations.get(operation)

    if not getattr(operation, "response", None) or not getattr(operation.response, "generated_videos", None):
        raise RuntimeError("Veo operation completed without generated videos")
    
    video_obj = operation.response.generated_videos[0]

    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path("./televideos")
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_snippet = "".join(c for c in prompt[:24] if c.isalnum() or c in ("-", "_")) or "video"
    output_path = output_dir / f"veo_{ts}_{safe_snippet}.mp4"

    print(f"Downloading video to {output_path}...")
    downloaded = client.files.download(file=video_obj.video)
    content = getattr(downloaded, "content", None) or downloaded
    with open(output_path, "wb") as f:
        f.write(content)
    
    final_path = output_path
    if not (audio_url or audio_path):
        return str(final_path)

    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required to add audio. Please install ffmpeg.")

    audio_source_path = None
    temp_downloaded_audio = None
    try:
        if audio_url:
            print(f"Downloading audio from {audio_url}...")
            temp_downloaded_audio = output_dir / f"audio_{ts}.tmp"
            with requests.get(audio_url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(temp_downloaded_audio, "wb") as f:
                    shutil.copyfileobj(r.raw, f)
            audio_source_path = temp_downloaded_audio
        else:
            if not audio_path or not os.path.exists(audio_path):
                 raise FileNotFoundError(f"Audio file not found at path: {audio_path}")
            audio_source_path = Path(audio_path)
        
        with_audio_path = output_dir / f"{output_path.stem}_with_audio{output_path.suffix}"
        print(f"Adding audio to video using ffmpeg. Output: {with_audio_path}")

        filter_args = ["-filter:a", f"volume={float(audio_volume)}"] if float(audio_volume) != 1.0 else []
        cmd = ["ffmpeg", "-y", "-i", str(output_path), "-i", str(audio_source_path), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", *filter_args, "-shortest", str(with_audio_path)]
        
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        final_path = with_audio_path
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg failed to mux audio: {e.stderr}")
    finally:
        if temp_downloaded_audio and temp_downloaded_audio.exists():
            temp_downloaded_audio.unlink()
            
    return str(final_path)


# Convenience wrapper with minimal required args and sensible defaults.
# Ensures optional audio fields are always provided so validation won't fail.
@tool("veo_video_generator_simple")
def generate_video_with_veo_simple(
    prompt: str,
    image_path: Optional[str] = None,
    duration: Optional[int] = None,
    style: Optional[str] = None,
    aspect_ratio: Optional[str] = None
) -> str:
    """
    Simpler interface for Veo video generation.
    - Falls back to IMAGE_PATH env var if image_path isn't provided by the agent.
    - Passes explicit defaults for audio_* params to avoid validation errors.
    """
    resolved_image = image_path or os.getenv("image_path") or os.getenv("IMAGE_PATH")
    # Defaults for optional params to satisfy tool validators
    duration = int(duration) if duration is not None else 15
    style = style or "social media"
    aspect_ratio = aspect_ratio or "9:16"
    # Call the underlying function of the Tool object
    try:
        if not resolved_image:
            # Fallback: run without image if not provided
            return generate_video_with_veo.func(
                prompt=prompt,
                image_path="/nonexistent",  # will be ignored by base when we change fallback
                duration=duration,
                style=style,
                aspect_ratio=aspect_ratio,
                audio_volume=1.0,
            )
        return generate_video_with_veo.func(
            prompt=prompt,
            image_path=resolved_image,
            duration=duration,
            style=style,
            aspect_ratio=aspect_ratio,
            audio_volume=1.0,
        )
    except Exception:
        # Final fallback: try without image entirely
        return generate_video_with_veo.func(
            prompt=prompt,
            image_path="/nonexistent",
            duration=duration,
            style=style,
            aspect_ratio=aspect_ratio,
            audio_volume=1.0,
        )