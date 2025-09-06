from typing import Optional
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import requests
import os
from datetime import datetime

class N8NReelPublishInput(BaseModel):
    """Input for the N8N Instagram Reel publishing tool."""
    video_path: str = Field(..., description="Path to the video file to be published")
    caption: str = Field(..., description="Caption for the Instagram reel")
    music_url: Optional[str] = Field(default=None, description="Optional background music URL")
    schedule_time: Optional[datetime] = Field(default=None, description="Optional scheduling time for the post")

class N8NReelPublisher(BaseTool):
    """Tool that publishes reels to Instagram using N8N workflow."""
    name: str = "n8n_reel_publisher"
    description: str = "Publish Instagram reels using N8N automation workflow"
    args_schema = N8NReelPublishInput

    def _run(
        self, 
        video_path: str, 
        caption: str, 
        music_url: Optional[str] = None,
        schedule_time: Optional[datetime] = None
    ) -> str:
        """
        Triggers the N8N workflow to publish an Instagram reel.
        
        Args:
            video_path (str): Path to the video file
            caption (str): Caption for the reel
            music_url (str, optional): URL to background music
            schedule_time (datetime, optional): When to publish the reel
            
        Returns:
            str: Status message
        """
        n8n_webhook_url = os.getenv("N8N_WEBHOOK_URL")
        if not n8n_webhook_url:
            raise ValueError("N8N_WEBHOOK_URL environment variable not set")

        payload = {
            "video_path": video_path,
            "caption": caption,
            "music_url": music_url,
            "schedule_time": schedule_time.isoformat() if schedule_time else None
        }

        try:
            response = requests.post(n8n_webhook_url, json=payload)
            response.raise_for_status()
            return f"Successfully triggered N8N workflow for reel publishing. Status: {response.status_code}"
        except requests.exceptions.RequestException as e:
            return f"Error triggering N8N workflow: {str(e)}"
