import os
from dotenv import load_dotenv
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai.tools import tool
from crewai_tools import WebsiteSearchTool,SerperDevTool

from typing import List, Optional
from pydantic import BaseModel, Field


from datetime import datetime as DateTime
from .tools.img_tool import generate_image_with_imagen, generate_video_with_veo, generate_video_with_veo_simple
from .tools.telegram_tool import (
    send_text_to_channel,
    send_photo_to_channel,
    send_video_to_channel,
    post_photo_story_as_user,
    post_video_story_as_user,
)

# Load environment variables
load_dotenv()

# Set up memory storage
STORAGE_DIR = os.path.join(os.path.dirname(__file__), "storage")
os.makedirs(STORAGE_DIR, exist_ok=True)
sdt = os.getenv("SERPER_API_KEY")
llma = LLM(
    api_key=os.getenv("GEMINI_API_KEY"),
    model="gemini/gemini-2.5-flash",
)
search_tool = SerperDevTool(api_key=sdt)
gapi = os.getenv("GEMINI_API_KEY")

### Pydantic models for structured outputs
class Captionoutput(BaseModel):
    caption: str
    contact_info: str

class Camera(BaseModel):
    angle: str = Field(..., description="Camera angle for the shot (e.g. medium-wide → close-up)")
    movement: str = Field(..., description="Camera movement style (e.g. slow dolly-in, orbit)")
    lens: str = Field(..., description="Lens specification, depth of field hints (e.g. 85mm, shallow DOF)")
    fps: int = Field(..., description="Frames per second — especially high for slow-motion")
    motion_style: Optional[str] = Field(None, description="Motion style descriptor (e.g. smooth slow-motion)")

class Action(BaseModel):
    actor_appearance: str = Field(..., description="Appearance / style of actor (clothing, demographic, etc.)")
    key_events: List[str] = Field(..., description="Ordered key events in the action sequence")
    blocking_notes: Optional[str] = Field(None, description="Notes about blocking / framing across the shot")

class Visuals(BaseModel):
    lighting: str = Field(..., description="Lighting style (warm rim, soft fill, high-key, etc.)")
    color_grade: Optional[str] = Field(None, description="Color grading or contrast style")
    effects: Optional[List[str]] = Field(None, description="List of visual effects, e.g. bokeh, vignetting")
    background: Optional[str] = Field(None, description="Background style (e.g. plain, minimalist studio)")
    focus_behavior: Optional[str] = Field(None, description="Focus behavior; what is sharp vs blurred")

class Audio(BaseModel):
    music_style: str = Field(..., description="Style / genre / mood of background music")
    sfx: Optional[List[str]] = Field(None, description="Sound-effects cues in the timeline")
    ambient: Optional[str] = Field(None, description="Ambient or environmental audio underlying the scene")

class Shot(BaseModel):
    id: str = Field(..., description="Unique identifier for the shot")
    duration_seconds: int = Field(..., description="Duration of this shot in seconds")
    role: str = Field(..., description="Role or purpose of the shot (narrative_lead, product_showcase, etc.)")
    description: str = Field(..., description="Textual description of what happens visually in the shot")
    camera: Camera = Field(..., description="Camera framing / movement details")
    action: Action = Field(..., description="Actor behaviour, events, and blocking details")
    visuals: Visuals = Field(..., description="Visual styling details")
    audio: Audio = Field(..., description="Audio / sound styling details")
    mood: Optional[str] = Field(None, description="Overall mood or tone for the shot (e.g. satirical, funny)")

class VoiceOver(BaseModel):
    text_template: str = Field(..., description="Voiceover text, possibly templated with placeholders")
    language: str = Field(..., description="Language in which voiceover should be delivered")
    voice_style: str = Field(..., description="Style of the narrator (e.g. satirical, confident, deadpan)")
    placement: str = Field(..., description="When / where the voiceover is placed within the video timeline")

class EndCardElements(BaseModel):
    logo: str = Field(..., description="Placement or description of logo in end card")
    tagline: str = Field(..., description="Text tagline to be shown in end card")
    cta: str = Field(..., description="Call-to-action text (e.g. 'Shop now')")

class EndCard(BaseModel):
    duration_seconds: int = Field(..., description="Duration of the end-card segment in seconds")
    elements: EndCardElements = Field(..., description="Elements to display in the end card")

class RenderSettings(BaseModel):
    resolution: str = Field(..., description="Video resolution (e.g. '1920x1080')")
    format: str = Field(..., description="File format (e.g. 'mp4')")
    fps: int = Field(..., description="Frames per second for rendering")
    seed: Optional[int] = Field(None, description="Random seed for reproducible rendering (if applicable)")

class Veo3PromptOutput(BaseModel):
    title: str = Field(..., description="Title of the prompt / video concept")
    duration_seconds: int = Field(..., description="Total duration targeted for the video in seconds")
    style: str = Field(..., description="Overall visual / narrative style descriptors")
    language: str = Field(..., description="Language placeholder or actual language for voiceover/text")
    shots: List[Shot] = Field(..., description="Sequence of shots/scenes composing the video")
    voiceover: VoiceOver = Field(..., description="Voiceover narration details")
    end_card: EndCard = Field(..., description="Details for the end-card segment including CTA")
    render_settings: RenderSettings = Field(..., description="Settings for final render (resolution, fps, etc.)")
    fallback_prompt: Optional[str] = Field(None, description="Plain-language fallback prompt if structured JSON not used")
    notes: Optional[List[str]] = Field(None, description="Additional instructions or reminders")


#Website search tool for Veo3 prompts
wstool = WebsiteSearchTool(config = dict(llm = dict(
    provider = "google",
    config = dict(model = "gemini/gemini-2.5-flash"),
), embedder = dict(
    provider = "google",
    config = dict(
        model = "models/gemini-embedding-001"
    ),
),),websites = "https://jzcreates.com/blog/7-incredible-google-veo-3-json-prompt-examples/")

wstool2 = WebsiteSearchTool(config = dict(llm = dict(
    provider = "google",
    config = dict(model = "gemini/gemini-2.5-flash"),
), embedder = dict(
    provider = "google",
    config = dict(
        model = "models/gemini-embedding-001"
    ),
),),websites = "https://www.imagine.art/blogs/veo-3-json-prompting-guide")

###Crew definition
@CrewBase
class SocialMediaPromotion():
    """SocialMediaPromotion crew for generating social media content"""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def __init__(self):
        # Load variables from .env file to be used for dereferencing
        self.user = os.getenv("user", "the user")
        self.cost = os.getenv("cost", "the cost")
        self.product_name = os.getenv("product_name", "our amazing product")
        self.product_description = os.getenv("product_description", "a detailed product description")
        self.user_story = os.getenv("user_story", "their personal journey and challenges")
        self.image_path = os.getenv("image_path", "")
        self.language = os.getenv("language", "English")
        print(f"DEBUG: Crew image_path set to: {self.image_path}")

    # Helper dictionary to pass all potential variables to format strings
    @property
    def _get_inputs(self):
        inputs = {
            'user': self.user,
            'cost': self.cost,
            'product_name': self.product_name,
            'description': self.product_description,
            'product_description': self.product_description, # Alias for consistency
            'user_story': self.user_story,
            'image_path': self.image_path,
            'language': self.language
        }
        print(f"DEBUG: _get_inputs returning: {inputs}")
        return inputs
    
    ### AGENTS
    @agent
    def summarizer(self) -> Agent:
        config = self.agents_config["summarizer"].copy()
        config['goal'] = config['goal'].format(**self._get_inputs)
        return Agent(
            config=config,
            verbose=True,
        )

    @agent
    def emotional_storyteller(self) -> Agent:
        config = self.agents_config["emotional_storyteller"].copy()
        config['goal'] = config['goal'].format(**self._get_inputs)
        return Agent(
            config = config,
            verbose = True,
        )

    @agent
    def optimal_price_generator(self) -> Agent:
        config = self.agents_config["optimal_price_generator"].copy()
        config['goal'] = config['goal'].format(**self._get_inputs)
        return Agent(
            config = config,
            tools = [search_tool],
            verbose = True,
        )
        

    @agent
    def product_image_generator(self) -> Agent:
        config = self.agents_config["product_image_generator"].copy()
        config['goal'] = config['goal'].format(**self._get_inputs)
        return Agent(
            config=config,
            verbose=True,
        )

    @agent
    def image_executor(self) -> Agent:
        config = self.agents_config["image_executor"].copy()
        config['goal'] = config['goal'].format(**self._get_inputs)
        return Agent(
            config=config,
            tools=[generate_image_with_imagen],
            verbose=True,
        )
    
    @agent
    def caption_generator(self) -> Agent:
        config = self.agents_config["caption_generator"].copy()
        config['goal'] = config['goal'].format(**self._get_inputs)
        return Agent(
            config=config,
            verbose=True,
        )

    @agent
    def instagram_post_generator(self) -> Agent:
        config = self.agents_config["instagram_post_generator"].copy()
        config['goal'] = config['goal'].format(**self._get_inputs)
        config['backstory'] = config['backstory'].format(**self._get_inputs)
        return Agent(
            config=config,
            tools=[generate_image_with_imagen],
            verbose=True,
        )

    @agent
    def instagram_reel_creator(self) -> Agent:
        config = self.agents_config["instagram_reel_creator"].copy()
        config['goal'] = config['goal'].format(**self._get_inputs)
        config['backstory'] = config['backstory'].format(**self._get_inputs)
        return Agent(
            config=config,
            tools=[generate_video_with_veo],
            verbose=True,
        )

    @agent
    def video_creator(self) -> Agent:
        config = self.agents_config["video_creator"].copy()
        config['goal'] = config['goal'].format(**self._get_inputs)
        config['backstory'] = config['backstory'].format(**self._get_inputs)
        return Agent(
            config=config,
            tools = [wstool,wstool2],
            verbose=True,
        )

    @agent
    def video_executor(self) -> Agent:
        config = self.agents_config["video_executor"].copy()
        config['goal'] = config['goal'].format(**self._get_inputs)
        return Agent(
            config=config,
            tools=[generate_video_with_veo_simple],
            verbose=True,
        )

    @agent
    def instagram_responder(self) -> Agent:
        config = self.agents_config["instagram_responder"].copy()
        config['goal'] = config['goal'].format(**self._get_inputs)
        config['backstory'] = config['backstory'].format(**self._get_inputs)
        return Agent(
            config=config,
            verbose=True,
        )
    
    @agent
    def telegram_channel_publisher(self) -> Agent:
        config = self.agents_config["telegram_channel_publisher"].copy()
        config['goal'] = config['goal'].format(**self._get_inputs)
        config['backstory'] = config['backstory'].format(**self._get_inputs)
        return Agent(
            config=config,
            tools=[send_text_to_channel, send_photo_to_channel, send_video_to_channel],
            verbose=True,
        )

    @agent
    def telegram_story_publisher(self) -> Agent:
        config = self.agents_config["telegram_story_publisher"].copy()
        config['goal'] = config['goal'].format(**self._get_inputs)
        return Agent(
            config=config,
            tools=[post_photo_story_as_user, post_video_story_as_user],
            verbose=True,
        )

    @agent
    def telegram_story_channel_publisher(self) -> Agent:
        config = self.agents_config["telegram_story_channel_publisher"].copy()
        config['goal'] = config['goal'].format(**self._get_inputs)
        config['backstory'] = config['backstory'].format(**self._get_inputs)
        return Agent(
            config=config,
            tools=[send_text_to_channel, send_photo_to_channel],
            verbose=True,
        )

    @agent
    def telegram_story_story_publisher(self) -> Agent:
        config = self.agents_config["telegram_story_story_publisher"].copy()
        config['goal'] = config['goal'].format(**self._get_inputs)
        config['backstory'] = config['backstory'].format(**self._get_inputs)
        return Agent(
            config=config,
            tools=[post_photo_story_as_user],
            verbose=True,
        )

    ### TASKS
    @task
    def summary_generator(self) -> Task:
        config = self.tasks_config["summary_generator"].copy()
        config['description'] = config['description'].format(**self._get_inputs)
        if 'expected_output' in config:
            config['expected_output'] = config['expected_output'].format(**self._get_inputs)
        return Task(config=config)

    

    @task
    def price_analysis_task(self) -> Task:
        config = self.tasks_config["price_analysis_task"].copy()
        config['description'] = config['description'].format(**self._get_inputs)
        if 'expected_output' in config:
            config['expected_output'] = config['expected_output'].format(**self._get_inputs)
        return Task(config=config)

    @task
    def story_advertising_task(self) -> Task:
        config = self.tasks_config["story_advertising_task"].copy()
        config['description'] = config['description'].format(**self._get_inputs)
        config['expected_output'] = config['expected_output'].format(**self._get_inputs)
        return Task(config=config)

    @task
    def generate_imagen_prompt(self) -> Task:
        config = self.tasks_config["generate_imagen_prompt"].copy()
        config['description'] = config['description'].format(**self._get_inputs)
        if 'expected_output' in config:
            config['expected_output'] = config['expected_output'].format(**self._get_inputs)
        return Task(config=config)

    @task
    def execute_image_generation(self) -> Task:
        config = self.tasks_config["execute_image_generation"].copy()
        if 'description' in config:
            config['description'] = config['description'].format(**self._get_inputs)
        if 'expected_output' in config:
            config['expected_output'] = config['expected_output'].format(**self._get_inputs)
        return Task(config=config)

    @task
    def generate_veo_prompt(self) -> Task:
        config = self.tasks_config["generate_veo_prompt"].copy()
        if 'description' in config:
            config['description'] = config['description'].format(**self._get_inputs)
        if 'expected_output' in config:
            config['expected_output'] = config['expected_output'].format(**self._get_inputs)
        return Task(config=config,output_json = Veo3PromptOutput)

    @task
    def execute_video_generation(self) -> Task:
        config = self.tasks_config["execute_video_generation"].copy()
        config['description'] = config['description'].format(**self._get_inputs)
        if 'expected_output' in config:
            config['expected_output'] = config['expected_output'].format(**self._get_inputs)
        return Task(config=config)

    @task
    def instagram_post_task(self) -> Task:
        config = self.tasks_config["instagram_post_task"].copy()
        config['description'] = config['description'].format(**self._get_inputs)
        config['expected_output'] = config['expected_output'].format(**self._get_inputs)
        return Task(config=config)

    @task
    def instagram_reel_task(self) -> Task:
        config = self.tasks_config["instagram_reel_task"].copy()
        config['description'] = config['description'].format(**self._get_inputs)
        config['expected_output'] = config['expected_output'].format(**self._get_inputs)
        return Task(config=config)

    @task
    def instagram_response_task(self) -> Task:
        config = self.tasks_config["instagram_response_task"].copy()
        config['description'] = config['description'].format(**self._get_inputs)
        if 'expected_output' in config:
            config['expected_output'] = config['expected_output'].format(**self._get_inputs)
        return Task(config=config)

    @task
    def telegram_channel_post_task(self) -> Task:
        config = self.tasks_config["telegram_channel_post_task"].copy()
        config['description'] = config['description'].format(**self._get_inputs)
        if 'expected_output' in config:
            config['expected_output'] = config['expected_output'].format(**self._get_inputs)
        return Task(config=config)
    
    @task
    def caption_generation(self) -> Task:
        config = self.tasks_config["caption_generation"].copy()
        config['description'] = config['description'].format(**self._get_inputs)
        if 'expected_output' in config:
            config['expected_output'] = config['expected_output'].format(**self._get_inputs)
        return Task(config=config, output_pydantic=Captionoutput)

    @task
    def telegram_story_task(self) -> Task:
        config = self.tasks_config["telegram_story_task"].copy()
        config['description'] = config['description'].format(**self._get_inputs)
        if 'expected_output' in config:
            config['expected_output'] = config['expected_output'].format(**self._get_inputs)
        return Task(config=config)

    @task
    def telegram_story_channel_post_task(self) -> Task:
        config = self.tasks_config["telegram_story_channel_post_task"].copy()
        config['description'] = config['description'].format(**self._get_inputs)
        config['expected_output'] = config['expected_output'].format(**self._get_inputs)
        return Task(config=config)

    @task
    def telegram_story_story_post_task(self) -> Task:
        config = self.tasks_config["telegram_story_story_post_task"].copy()
        config['description'] = config['description'].format(**self._get_inputs)
        config['expected_output'] = config['expected_output'].format(**self._get_inputs)
        return Task(config=config)

    @crew
    def crew_without_image(self) -> Crew:
        """Sequence when image is NOT provided: includes image generation via Instagram post, then reel and publishing."""
        return Crew(
            agents=[
                self.summarizer(),
                self.caption_generator(),
                self.product_image_generator(),
                self.image_executor(),
                self.video_creator(),
                self.video_executor(),
                self.telegram_channel_publisher(),
                self.telegram_story_publisher(),
            ],
            tasks=[
                self.summary_generator(),
                self.caption_generation(),
                self.generate_imagen_prompt(),
                self.execute_image_generation(),
                self.generate_veo_prompt(),
                self.execute_video_generation(),
                self.telegram_channel_post_task(),
                self.telegram_story_task(),
            ],
            process=Process.sequential,
            verbose=True,
            llm=llma
        )

    @crew
    def crew_with_image(self) -> Crew:
        """Sequence when image IS provided: skip image generation and go straight to reel and publishing."""
        return Crew(
            agents=[
                self.summarizer(),
                self.caption_generator(),
                self.video_creator(),
                self.video_executor(),
                self.telegram_channel_publisher(),
                self.telegram_story_publisher(),
            ],
            tasks=[
                self.summary_generator(),
                self.caption_generation(),
                self.generate_veo_prompt(),
                self.execute_video_generation(),
                self.telegram_channel_post_task(),
                self.telegram_story_task(),
            ],
            process=Process.sequential,
            verbose=True,
            llm=llma
        )

    @crew
    def crew_price_generation(self) -> Crew:
        """Crew for optimal price generation based on product details."""
        return Crew(
            agents=[
                self.optimal_price_generator(),
            ],
            tasks=[
                self.price_analysis_task(),
            ],
            process=Process.sequential,
            verbose=True,
            llm=llma
        )

    @crew
    def crew_story_advertising(self) -> Crew:
        """Crew for emotional story creation and Telegram publishing."""
        return Crew(
            agents=[
                self.emotional_storyteller(),
                self.telegram_story_channel_publisher(),
                self.telegram_story_story_publisher(),
            ],
            tasks=[
                self.story_advertising_task(),
                self.telegram_story_channel_post_task(),
                self.telegram_story_story_post_task(),
            ],
            process=Process.sequential,
            verbose=True,
            llm=llma
        )
    
    
