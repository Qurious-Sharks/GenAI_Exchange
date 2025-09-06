import os
from dotenv import load_dotenv
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai.tools import tool
from crewai.memory import LongTermMemory, ShortTermMemory
from crewai.memory.storage.rag_storage import RAGStorage
from crewai.memory.storage.ltm_sqlite_storage import LTMSQLiteStorage
from pydantic import BaseModel
from datetime import datetime as DateTime
from .tools.custom_tool import ImagenImageGenerator, VeoVideoGenerator
from .tools.n8n_tool import N8NReelPublisher

# Load environment variables
load_dotenv()

# Set up memory storage
STORAGE_DIR = os.path.join(os.path.dirname(__file__), "storage")
os.makedirs(STORAGE_DIR, exist_ok=True)

llma = LLM(
    api_key=os.getenv("GEMINI_API_KEY"),
    model="gemini/gemini-2.5-flash",
)

gapi = os.getenv("GEMINI_API_KEY")

# Memory configurations
WEEK_MEMORY = LongTermMemory(
    storage=LTMSQLiteStorage(
        db_path=f"{STORAGE_DIR}/week_memory.db"
    )
)

emconfig = {
    "provider": "google",
    "config": {
        "api_key": gapi,
        "model": "models/gemini-embedding-001"
    }
}

SHORT_TERM_MEMORY = ShortTermMemory(
    storage=RAGStorage(
        embedder_config=emconfig,
        type="short_term",
        path="./memory/"
    )
)

# Pydantic output objects
class SocialMediaContent(BaseModel):
    date: DateTime
    story: str
    product_summary: str
    instagram_post: str
    instagram_reel: str
    whatsapp_status: str
    image_path: str

@CrewBase
class SocialMediaPromotion():
    """SocialMediaPromotion crew for generating social media content"""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def storyteller(self) -> Agent:
        return Agent(
            config=self.agents_config["storyteller"],
            verbose=True,
            memory=SHORT_TERM_MEMORY
        )

    @agent
    def summarizer(self) -> Agent:
        return Agent(
            config=self.agents_config["summarizer"],
            verbose=True,
            memory=SHORT_TERM_MEMORY
        )

    @agent
    def instagram_post_generator(self) -> Agent:
        return Agent(
            config=self.agents_config["instagram_post_generator"],
            tools=[ImagenImageGenerator()],
            verbose=True,
            memory=WEEK_MEMORY
        )

    @agent
    def instagram_reel_creator(self) -> Agent:
        return Agent(
            config=self.agents_config["instagram_reel_creator"],
            tools=[VeoVideoGenerator()],
            verbose=True,
            memory=WEEK_MEMORY
        )

    @agent
    def whatsapp_status_generator(self) -> Agent:
        return Agent(
            config=self.agents_config["whatsapp_status_generator"],
            tools=[VeoVideoGenerator()],
            verbose=True,
            memory=WEEK_MEMORY
        )

    @agent
    def whatsapp_responder(self) -> Agent:
        return Agent(
            config=self.agents_config["whatsapp_responder"],
            verbose=True,
            memory=SHORT_TERM_MEMORY
        )

    @agent
    def instagram_responder(self) -> Agent:
        return Agent(
            config=self.agents_config["instagram_responder"],
            verbose=True,
            memory=SHORT_TERM_MEMORY
        )

    @agent
    def instagram_publisher(self) -> Agent:
        return Agent(
            config=self.agents_config["instagram_publisher"],
            tools=[N8NReelPublisher()],
            verbose=True,
            memory=SHORT_TERM_MEMORY
        )

    @task
    def storytelling_task(self) -> Task:
        return Task(
            config=self.tasks_config["storytelling_task"],
            output_pydantic=SocialMediaContent
        )

    @task
    def summarize_product_task(self) -> Task:
        return Task(
            config=self.tasks_config["summarize_product_task"],
            output_pydantic=SocialMediaContent
        )

    @task
    def instagram_post_task(self) -> Task:
        return Task(
            config=self.tasks_config["instagram_post_task"],
            output_pydantic=SocialMediaContent
        )

    @task
    def instagram_reel_task(self) -> Task:
        return Task(
            config=self.tasks_config["instagram_reel_task"],
            output_pydantic=SocialMediaContent
        )

    @task
    def whatsapp_status_task(self) -> Task:
        return Task(
            config=self.tasks_config["whatsapp_status_task"],
            output_pydantic=SocialMediaContent
        )

    @task
    def publish_reel_task(self) -> Task:
        return Task(
            config=self.tasks_config["publish_reel_task"],
            output_pydantic=SocialMediaContent,
            context={
                "reel_content": "{{instagram_reel_task.output}}"
            }
        )

    @crew
    def crew(self) -> Crew:
        """Creates the SocialMediaPromotion crew that handles the creation of social media content"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
            memory=True,
            long_term_memory=LongTermMemory(
                storage=LTMSQLiteStorage(
                    db_path=f"{STORAGE_DIR}/crew_memory.db"
                )
            ),
            embedder={
                "provider": "google",
                "config": {
                    "api_key": gapi,
                    "model": "models/gemini-embedding-001"
                }
            },
            llm=llma
        )
