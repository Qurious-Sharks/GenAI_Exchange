import os
from dotenv import load_dotenv
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai.tools import tool
from crewai_tools import WebsiteSearchTool,SerperDevTool


# Memory features removed
from pydantic import BaseModel
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

class Captionoutput(BaseModel):
    caption: str
    contact_info: str

wstool = WebsiteSearchTool(config = dict(llm = dict(
    provider = "google",
    config = dict(model = "gemini/gemini-2.5-flash"),
), embedder = dict(
    provider = "google",
    config = dict(
        model = "models/gemini-embedding-001"
    ),
),),website = "https://www.powtoon.com/blog/veo-3-video-prompt-examples/")

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
            'image_path': self.image_path
        }
        print(f"DEBUG: _get_inputs returning: {inputs}")
        return inputs

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
        return Agent(
        config = self.agents_config["optimal_price_generator"],
        tools = [search_tool],
        verbose = True,
        )
        

    @agent
    def product_image_generator(self) -> Agent:
        return Agent(
            config=self.agents_config["product_image_generator"],
            verbose=True,
        )

    @agent
    def image_executor(self) -> Agent:
        return Agent(
            config=self.agents_config["image_executor"],
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
            tools = [wstool],
            verbose=True,
        )

    @agent
    def video_executor(self) -> Agent:
        return Agent(
            config=self.agents_config["video_executor"],
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
        return Task(config=config)

    

    @task
    def price_analysis_task(self) -> Task:
        config = self.tasks_config["price_analysis_task"].copy()
        config['description'] = config['description'].format(**self._get_inputs)
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
        return Task(config=config)

    @task
    def execute_image_generation(self) -> Task:
        return Task(
            config=self.tasks_config["execute_image_generation"],
        )

    @task
    def generate_veo_prompt(self) -> Task:
        return Task(
            config=self.tasks_config["generate_veo_prompt"],
        )

    @task
    def execute_video_generation(self) -> Task:
        config = self.tasks_config["execute_video_generation"].copy()
        config['description'] = config['description'].format(**self._get_inputs)
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
        return Task(config=config)

    @task
    def telegram_channel_post_task(self) -> Task:
        config = self.tasks_config["telegram_channel_post_task"].copy()
        config['description'] = config['description'].format(**self._get_inputs)
        return Task(config=config)
    
    @task
    def caption_generation(self) -> Task:
        config = self.tasks_config["caption_generation"].copy()
        config['description'] = config['description'].format(**self._get_inputs)
        return Task(config=config, output_pydantic=Captionoutput)

    @task
    def telegram_story_task(self) -> Task:
        config = self.tasks_config["telegram_story_task"].copy()
        config['description'] = config['description'].format(**self._get_inputs)
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
    
    
