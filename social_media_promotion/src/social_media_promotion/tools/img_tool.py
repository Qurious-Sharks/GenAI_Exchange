import os
import time
import base64
from datetime import datetime
from pathlib import Path
from typing import Optional
import requests
import shutil
import subprocess
from crewai.tools import tool
from google.genai.types import Image

FFMPEG_PATH = r"F:\ffmpeg\ffmpeg-master-latest-win64-gpl-shared\bin"
WEB_UPLOADS_DIR = Path(__file__).parent / "shop_data" / "static" / "uploads"

def copy_image_to_web_dir(image_path: str) -> str:
    """Copy image from gradio images directory to web-accessible directory."""
    if not image_path or not os.path.exists(image_path):
        return ""
    
    filename = os.path.basename(image_path)
    web_path = WEB_UPLOADS_DIR / filename
    
    try:
        # Copy the file
        shutil.copy2(image_path, web_path)
        print(f"✅ Image copied to web directory: {web_path}")
        return str(web_path)
    except Exception as e:
        print(f"⚠️ Could not copy image to web directory: {e}")
        return image_path

try:
    from google import genai
except ImportError:
    class _GenAIStub:
        Client = None
    genai = _GenAIStub()

os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "false")

@tool("veo_video_generator")
def generate_video_with_veo(
    prompt: str,
    image_path: Optional[str] = None,
    duration: int = 15,
    style: str = "social media",
    aspect_ratio: str = "9:16",
    audio_path: Optional[str] = None,
    audio_url: Optional[str] = None,
    audio_volume: float = 1.0
) -> str:
    """Generates a video from a text prompt and optional image using Veo 3 API."""
    gapi = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not gapi:
        raise ValueError("Missing GEMINI_API_KEY or GOOGLE_API_KEY")
    if getattr(genai, "Client", None) is None:
        raise ImportError("Install with: pip install google-genai")

    client = genai.Client(api_key=gapi, vertexai=False)

    # Handle image input - use proper Image class format
    if image_path and os.path.exists(image_path):
        # For uploaded images, use the Image class with image_bytes
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        
        # Determine MIME type based on file extension
        mime_type = "image/jpeg"
        if image_path.lower().endswith(".png"):
            mime_type = "image/png"
        elif image_path.lower().endswith(".webp"):
            mime_type = "image/webp"
        
        # Use the Image class for Veo API
        image_for_video = Image(
            image_bytes=image_bytes,
            mime_type=mime_type
        )
    else:
        # Generate an image using Imagen when not provided
        imagen = client.models.generate_images(
            model="imagen-4.0-generate-001",
            prompt=prompt
        )
        if not getattr(imagen, "generated_images", None):
            raise RuntimeError("Imagen API call returned no images for Veo input")
        # Use the generated image object directly
        image_for_video = imagen.generated_images[0].image

    operation = client.models.generate_videos(
        model="veo-3.0-generate-001",
        prompt=prompt,
        image=image_for_video,
    )

    while not getattr(operation, "done", False):
        time.sleep(10)
        operation = client.operations.get(operation)

    video_obj = operation.response.generated_videos[0]
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path("./videos")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"veo_{ts}.mp4"
    
    # Download the generated video with proper error handling
    try:
        video_data = client.files.download(file=video_obj.video)
        with open(output_path, 'wb') as f:
            f.write(video_data)
        
        # Verify the file was created and has content
        if output_path.exists() and output_path.stat().st_size > 0:
            print(f"✅ Video successfully generated: {output_path}")
            return str(output_path)
        else:
            print(f"❌ Video file was not created properly: {output_path}")
            raise Exception("Video file creation failed")
    except Exception as download_error:
        print(f"❌ Error downloading video: {download_error}")
        raise download_error


@tool("veo_video_generator_simple")
def generate_video_with_veo_simple(prompt: str) -> list[str]:
    """Simplified wrapper for Veo video generation with default parameters.
    
    Returns:
        [video_path, image_path]
        - video_path: str, path to the generated (or fallback) video
        - image_path: str, path to generated image if created internally, else ""
    """
    gapi = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not gapi:
        print("No API key found, using fallback video")
        return [_create_fallback_video(), ""]

    if getattr(genai, "Client", None) is None:
        print("Google GenAI not available, using fallback video")
        return [_create_fallback_video(), ""]

    try:
        client = genai.Client(api_key=gapi, vertexai=False)

        image_path = os.getenv("IMAGE_PATH", "")
        image_for_video = None
        generated_image_path = ""

        if image_path and os.path.exists(image_path):
            print(f"Using uploaded image for video: {image_path}")
            with open(image_path, "rb") as f:
                image_bytes = f.read()

            mime_type = "image/jpeg"
            if image_path.lower().endswith(".png"):
                mime_type = "image/png"
            elif image_path.lower().endswith(".webp"):
                mime_type = "image/webp"

            image_for_video = Image(image_bytes=image_bytes, mime_type=mime_type)
            generated_image_path = image_path
        else:
            # Generate a new image
            print("No uploaded image found, generating new image for video...")
            imagen_result = client.models.generate_images(
                model="imagen-4.0-generate-001",
                prompt=f"{prompt}, high quality, cinematic style"
            )

            if not imagen_result.generated_images:
                print("Image generation failed, using fallback")
                return [_create_fallback_video(), ""]

            generated_image = imagen_result.generated_images[0].image
            image_for_video = imagen_result.generated_images[0].image
            ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            img_dir = Path("./images")
            img_dir.mkdir(parents=True, exist_ok=True)
            generated_image_path = img_dir / f"imagen_generated_{ts}.png"
            dum_path = copy_image_to_web_dir(str(generated_image_path))
            try:
                image_bytes = generated_image.image_bytes
                with open(generated_image_path, "wb") as f:
                    f.write(image_bytes)
                print(f"Generated image saved: {generated_image_path}")

            except Exception as img_error:
                print(f"Error saving generated image: {img_error}")
                return [_create_fallback_video(), ""]

        # Generate video with Veo
        print("Generating video with Veo...")
        operation = client.models.generate_videos(
            model="veo-3.0-generate-001",
            prompt=prompt,
            image=image_for_video,
        )

        # Wait for completion
        print("Waiting for video generation...")
        max_wait = 300
        wait_time = 0
        while not getattr(operation, "done", False) and wait_time < max_wait:
            time.sleep(10)
            wait_time += 10
            try:
                operation = client.operations.get(operation)
                print(f"Video generation in progress... ({wait_time}s)")
            except Exception as e:
                print(f"Error checking operation status: {e}")
                break

        if not getattr(operation, "done", False):
            print("Video generation timed out, using fallback")
            return [_create_fallback_video(), str(generated_image_path)]

        if not hasattr(operation, 'response') or not hasattr(operation.response, 'generated_videos'):
            print("No video generated, using fallback")
            return [_create_fallback_video(), str(generated_image_path)]

        video_obj = operation.response.generated_videos[0]
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        output_dir = Path("./videos")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"veo_generated_{ts}.mp4"

        print(f"Downloading generated video to {output_path}")
        try:
            video_data = client.files.download(file=video_obj.video)
            with open(output_path, 'wb') as f:
                f.write(video_data)

            if output_path.exists() and output_path.stat().st_size > 0:
                print(f"✅ Video successfully generated: {output_path}")
                return [str(output_path), str(generated_image_path)]
            else:
                print(f"❌ Video file was not created properly: {output_path}")
                return [_create_fallback_video(), str(generated_image_path)]
        except Exception as download_error:
            print(f"❌ Error downloading video: {download_error}")
            return [_create_fallback_video(), str(generated_image_path)]

    except Exception as e:
        print(f"Veo video generation failed: {e}")
        return [_create_fallback_video(), ""]

def _create_fallback_video():
    """Create a fallback video when Veo generation fails."""
    fallback_dir = Path("./videos")
    fallback_dir.mkdir(parents=True, exist_ok=True)
    
    # Use existing sample video if available
    sample_video = fallback_dir / "product_video.mp4"
    if sample_video.exists():
        print(f"Using existing sample video: {sample_video}")
        return str(sample_video)
    
    # Create a new sample video using ffmpeg
    try:
        import subprocess
        import shutil
        
        # Find ffmpeg executable
        ffmpeg_cmd = shutil.which('ffmpeg')
        if not ffmpeg_cmd:
            # Try common Windows paths
            if os.name == 'nt':
                ffmpeg_cmd = r"F:\ffmpeg\ffmpeg-master-latest-win64-gpl-shared\bin\ffmpeg.exe"
                if not os.path.exists(ffmpeg_cmd):
                    ffmpeg_cmd = 'ffmpeg'
            else:
                ffmpeg_cmd = '/opt/homebrew/bin/ffmpeg'
        
        print(f"Creating fallback video using: {ffmpeg_cmd}")
        result = subprocess.run([
            ffmpeg_cmd, '-f', 'lavfi', '-i', 'testsrc=duration=10:size=720x1280:rate=30', 
            '-f', 'lavfi', '-i', 'sine=frequency=1000:duration=10', 
            '-c:v', 'libx264', '-c:a', 'aac', '-shortest', str(sample_video), '-y'
        ], check=True, capture_output=True, text=True)
        
        if sample_video.exists() and sample_video.stat().st_size > 0:
            print(f"✅ Created new fallback video: {sample_video}")
            return str(sample_video)
        else:
            print(f"❌ Fallback video creation failed - file not created")
            return ""
    except Exception as ffmpeg_error:
        print(f"❌ Fallback video creation failed: {ffmpeg_error}")
        return ""