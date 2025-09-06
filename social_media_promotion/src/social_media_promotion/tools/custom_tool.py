from langchain.tools import BaseTool
from typing import Optional, Type
from pydantic import BaseModel, Field
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import requests
import shutil
import subprocess
try:
    from google import genai  # type: ignore
except Exception:
    # Provide a lightweight stub so tests can patch genai.Client without the package installed
    class _GenAIStub:
        Client = None
    genai = _GenAIStub()  # type: ignore

class ImagePromptInput(BaseModel):
    """Input for the Imagen image generation tool."""
    prompt: str = Field(..., description="The prompt to generate the image from")
    style: Optional[str] = Field(default="photorealistic", description="The style of the image to generate")

class VideoPromptInput(BaseModel):
    """Input for the Veo video generation tool."""
    prompt: str = Field(..., description="The prompt to generate the video from")
    duration: int = Field(default=15, description="Duration of the video in seconds")
    style: Optional[str] = Field(default="social media", description="The style of the video")
    image_path: Optional[str] = Field(default=None, description="Optional path to an input image to guide the video")
    aspect_ratio: Optional[str] = Field(default="9:16", description="Aspect ratio such as 9:16, 1:1, 16:9")
    audio_path: Optional[str] = Field(default=None, description="Optional local path to a background audio file")
    audio_url: Optional[str] = Field(default=None, description="Optional URL to a background audio file to download and use")
    audio_volume: Optional[float] = Field(default=1.0, description="Audio volume multiplier, e.g., 0.8 for -20% or 1.2 for +20%")

class ImagenImageGenerator(BaseTool):
    """Tool that generates images using Google's Imagen model."""
    name: str = "imagen_image_generator"
    description: str = "Generate photorealistic images using Google's Imagen model"
    args_schema: Type[BaseModel] = ImagePromptInput

    def _run(self, prompt: str, style: Optional[str] = "photorealistic") -> str:
        """
        Run the image generation.
        
        Args:
            prompt (str): The prompt to generate the image from
            style (str, optional): The style of the image. Defaults to "photorealistic".
            
        Returns:
            str: Path to the generated image
        """
        # TODO: Implement actual Imagen API call
        # This is a placeholder that would be replaced with actual Imagen integration
        print(f"Generating image with prompt: {prompt} in style: {style}")
        return "path/to/generated/image.jpg"

class VeoVideoGenerator(BaseTool):
    """Tool that generates videos using Veo 3."""
    name: str = "veo_video_generator"
    description: str = "Generate professional videos using Veo 3"
    args_schema: Type[BaseModel] = VideoPromptInput

    def _run(self, prompt: str, duration: int = 15, style: Optional[str] = "social media", image_path: Optional[str] = None, aspect_ratio: Optional[str] = "9:16", audio_path: Optional[str] = None, audio_url: Optional[str] = None, audio_volume: Optional[float] = 1.0) -> str:
        """
        Run the video generation.
        
        Args:
            prompt (str): The prompt to generate the video from
            duration (int, optional): Duration in seconds. Defaults to 15.
            style (str, optional): The style of the video. Defaults to "social media".
            image_path (str, optional): Local path to an image to condition the video
            aspect_ratio (str, optional): Aspect ratio for the video, e.g., 9:16
            
        Returns:
            str: Path to the generated video (with audio if provided)
        """
        # Initialize Google GenAI client
        gapi = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not gapi:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY environment variable not set")

        if getattr(genai, "Client", None) is None:
            raise ImportError("google-genai is not installed. Install with: pip install google-genai")
        client = genai.Client(api_key=gapi)

        # Prepare optional image input
        image_for_video = None
        if image_path:
            # Upload user-provided image
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"Image not found at {image_path}")
            uploaded = client.files.upload(file=image_path)
            image_for_video = uploaded
        else:
            # Generate an image first using Imagen
            imagen = client.models.generate_images(
                model="imagen-3.0-generate-002",
                prompt=prompt,
            )
            if not getattr(imagen, "generated_images", None):
                raise RuntimeError("Imagen did not return any images")
            image_for_video = imagen.generated_images[0].image

        # Generate video with Veo 3 using the image and prompt
        operation = client.models.generate_videos(
            model="veo-3.0-generate-preview",
            prompt=f"{prompt}\nStyle: {style}\nAspect Ratio: {aspect_ratio}",
            image=image_for_video,
        )

        # Poll until completion
        poll_interval_s = float(os.getenv("VEO_POLL_INTERVAL_SECONDS", "10"))
        timeout_s = int(os.getenv("VEO_TIMEOUT_SECONDS", "900"))
        start_time = time.time()
        while not getattr(operation, "done", False):
            if time.time() - start_time > timeout_s:
                raise TimeoutError("Veo video generation timed out")
            time.sleep(poll_interval_s)
            operation = client.operations.get(operation)

        if not getattr(operation, "response", None) or not getattr(operation.response, "generated_videos", None):
            raise RuntimeError("Veo operation completed without generated videos")

        video_obj = operation.response.generated_videos[0]

        # Prepare output path
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        output_dir = Path(os.getenv("VEO_OUTPUT_DIR", "/Users/hemasurya/Desktop/GenAI_Exchange/social_media_promotion/src/social_media_promotion/storage/videos"))
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_snippet = "".join(c for c in prompt[:24] if c.isalnum() or c in ("-", "_")) or "video"
        output_path = output_dir / f"veo_{ts}_{safe_snippet}.mp4"

        # Download and save
        downloaded = client.files.download(file=video_obj.video)
        # Try to support both object and bytes-like returns
        saved = False
        try:
            # Newer SDKs expose a save() method
            if hasattr(downloaded, "save"):
                downloaded.save(str(output_path))
                saved = True
        except Exception:
            pass
        if not saved:
            try:
                content = getattr(downloaded, "content", None) or downloaded
                # If it's a requests-like Response
                if hasattr(downloaded, "iter_content"):
                    with open(output_path, "wb") as f:
                        for chunk in downloaded.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                f.write(chunk)
                    saved = True
                elif isinstance(content, (bytes, bytearray)):
                    with open(output_path, "wb") as f:
                        f.write(content)
                    saved = True
            except Exception as e:
                raise RuntimeError(f"Failed to save Veo video: {e}")

        # If audio provided, mux it into the video using ffmpeg
        final_path = output_path
        temp_downloaded_audio: Optional[Path] = None

        if audio_url or audio_path:
            if shutil.which("ffmpeg") is None:
                raise RuntimeError("ffmpeg is required to add audio. Please install ffmpeg or omit audio inputs.")

            # Resolve audio source
            audio_source_path: Path
            if audio_url:
                try:
                    temp_downloaded_audio = output_dir / f"audio_{ts}.tmp"
                    with requests.get(audio_url, stream=True, timeout=60) as r:
                        r.raise_for_status()
                        with open(temp_downloaded_audio, "wb") as f:
                            for chunk in r.iter_content(chunk_size=1024 * 64):
                                if chunk:
                                    f.write(chunk)
                    audio_source_path = temp_downloaded_audio
                except Exception as e:
                    raise RuntimeError(f"Failed to download audio from URL: {e}")
            else:
                if not audio_path or not os.path.exists(audio_path):
                    raise FileNotFoundError(f"Audio file not found at {audio_path}")
                audio_source_path = Path(audio_path)

            # Produce output filename with audio suffix
            with_audio_path = output_dir / f"{output_path.stem}_with_audio{output_path.suffix}"

            # Build ffmpeg command
            # -shortest ensures output ends when the shortest stream ends (video duration preserved)
            filter_args = []
            if audio_volume is not None and float(audio_volume) != 1.0:
                filter_args = ["-filter:a", f"volume={float(audio_volume)}"]

            cmd = [
                "ffmpeg", "-y",
                "-i", str(output_path),
                "-i", str(audio_source_path),
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                *filter_args,
                "-shortest",
                str(with_audio_path)
            ]

            try:
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"ffmpeg failed to mux audio: {e.stderr.decode(errors='ignore')}")
            finally:
                if temp_downloaded_audio and temp_downloaded_audio.exists():
                    try:
                        temp_downloaded_audio.unlink()
                    except Exception:
                        pass

            final_path = with_audio_path

        return str(final_path)
