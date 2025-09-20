import os
import warnings
from datetime import datetime
from dotenv import load_dotenv
from social_media_promotion.crew import SocialMediaPromotion
import shutil
from pathlib import Path

load_dotenv()

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")
warnings.filterwarnings("ignore", category=DeprecationWarning)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")
IMAGES_DIR = Path(__file__).parent / "images"
WEB_UPLOADS_DIR = Path(__file__).parent / "shop_data" / "static" / "uploads"

def assign_output_files():
    """Ensure output directory exists and any output file paths are set up."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    WEB_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

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

def add_product_to_website(user_name: str, product_name: str, product_details: str, image_path: str = "", price: str = "0"):
    """Add a product to the website database."""
    try:
        # Import here to avoid circular imports
        from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, ForeignKey, UniqueConstraint
        from sqlalchemy.orm import declarative_base, sessionmaker, relationship
        from pathlib import Path
        
        # Database setup
        BASE_DIR = Path(__file__).parent
        DATA_DIR = BASE_DIR / "shop_data"
        engine = create_engine(f"sqlite:///{DATA_DIR}/shop.db")
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base = declarative_base()
        
        # User model
        class User(Base):
            __tablename__ = "users"
            id = Column(Integer, primary_key=True, index=True)
            username = Column(String, unique=True, index=True)
            password = Column(String)
            is_admin = Column(Boolean, default=False)
            session_id = Column(String, unique=True, nullable=True)
            products = relationship("Product", back_populates="user")
        
        # Product model
        class Product(Base):
            __tablename__ = "products"
            id = Column(Integer, primary_key=True, index=True)
            name = Column(String, index=True)
            details = Column(Text)
            price = Column(String)
            image_path = Column(String)
            user_id = Column(Integer, ForeignKey("users.id"))
            user = relationship("User", back_populates="products")
            __table_args__ = (UniqueConstraint('user_id', 'name', name='unique_user_product'),)
        
        # Create tables
        Base.metadata.create_all(bind=engine)
        
        db = SessionLocal()
        
        # Find or create user
        user = db.query(User).filter(User.username == user_name).first()
        if not user:
            user = User(username=user_name, password="", is_admin=False)
            db.add(user)
            db.commit()
            db.refresh(user)
        
        # Check if product already exists
        existing_product = db.query(Product).filter(
            Product.user_id == user.id,
            Product.name == product_name
        ).first()
        
        if existing_product:
            print(f"⚠️ Product '{product_name}' already exists for user '{user_name}'")
            db.close()
            return
        
        # Create product
        product = Product(
            name=product_name,
            details=product_details,
            price=price,
            image_path=os.path.basename(image_path) if image_path else "",
            user_id=user.id
        )
        
        db.add(product)
        db.commit()
        db.close()
        
        print(f"✅ Product '{product_name}' added to website for user '{user_name}'")
        
    except Exception as e:
        print(f"⚠️ Could not add product to website: {e}")

def run_promotion_pipeline(inputs=None):
    """Runs the promotion workflow choosing the crew based on whether an image path is provided."""
    print("Running the social media promotion workflow...")

    if inputs is None:
        inputs = {
            'current_year': str(datetime.now().year)
        }

    assign_output_files()
    try:
        if inputs:
            user_val = str(inputs.get("user") or inputs.get("user_name") or "").strip()
            cost_val = str(inputs.get("cost") or "").strip()
            prod_val = str(inputs.get("product_name") or "").strip()
            desc_val = str(inputs.get("product_description") or inputs.get("product_details") or "").strip()
            lang_val = str(inputs.get("language") or "").strip()
            img_val = str(inputs.get("image_path") or inputs.get("product_image_path") or "").strip()

            if user_val:
                os.environ["user"] = user_val
            if cost_val:
                os.environ["cost"] = cost_val
            if prod_val:
                os.environ["product_name"] = prod_val
            if desc_val:
                os.environ["product_description"] = desc_val
            if img_val:
                # Copy image to web directory if it exists
                web_image_path = copy_image_to_web_dir(img_val)
                os.environ["image_path"] = web_image_path
            if lang_val:
                os.environ["language"] = lang_val

        # Instantiate after env is ready
        crew_instance = SocialMediaPromotion()
        crew_without_image = crew_instance.crew_without_image()
        crew_with_image = crew_instance.crew_with_image()

        image_path = (inputs or {}).get("product_image_path") or (inputs or {}).get("image_path") or os.getenv("image_path")
        if image_path:
            result = crew_with_image.kickoff(inputs=inputs)
        else:
            result = crew_without_image.kickoff(inputs=inputs)
        print("✅ Workflow complete.\n")
        print(result)
        
        # Add product to website database
        if inputs:
            user_name = str(inputs.get("user") or inputs.get("user_name") or "").strip()
            product_name = str(inputs.get("product_name") or "").strip()
            product_details = str(inputs.get("product_description") or inputs.get("product_details") or "").strip()
            image_path = os.getenv("image_path", "")
            cost_val = os.getenv("cost", "0")  # Get price from environment
            
            if user_name and product_name and product_details:
                add_product_to_website(user_name, product_name, product_details, image_path, cost_val)
        
        return result
    except Exception as e:
        print(f"❌ Error in workflow: {str(e)}")
        raise e
    finally:
        # Preserve images for downstream shopping site usage
        pass

def run_price_generation_pipeline(inputs=None):
    """Runs the price generation workflow."""
    print("Running the price generation workflow...")

    if inputs is None:
        inputs = {
            'current_year': str(datetime.now().year)
        }

    assign_output_files()
    try:
        if inputs:
            user_val = str(inputs.get("user") or inputs.get("user_name") or "").strip()
            prod_val = str(inputs.get("product_name") or "").strip()
            desc_val = str(inputs.get("product_description") or inputs.get("product_details") or "").strip()
            lang_val = str(inputs.get("language") or "").strip()

            if user_val:
                os.environ["user"] = user_val
            if prod_val:
                os.environ["product_name"] = prod_val
            if desc_val:
                os.environ["product_description"] = desc_val
            if lang_val:
                os.environ["language"] = lang_val

        # Instantiate after env is ready
        crew_instance = SocialMediaPromotion()
        crew_price_generation = crew_instance.crew_price_generation()

        result = crew_price_generation.kickoff(inputs=inputs)
        print("✅ Price generation workflow complete.\n")
        print(result)
        return result
    except Exception as e:
        print(f"❌ Error in price generation workflow: {str(e)}")
        raise e

def run_story_advertising_pipeline(inputs=None):
    """Runs the story advertising workflow."""
    print("Running the story advertising workflow...")

    if inputs is None:
        inputs = {
            'current_year': str(datetime.now().year)
        }

    assign_output_files()
    try:
        if inputs:
            user_val = str(inputs.get("user") or inputs.get("user_name") or "").strip()
            story_val = str(inputs.get("user_story") or "").strip()
            prod_val = str(inputs.get("product_name") or "").strip()
            desc_val = str(inputs.get("product_description") or inputs.get("product_details") or "").strip()
            img_val = str(inputs.get("image_path") or inputs.get("product_image_path") or "").strip()
            lang_val = str(inputs.get("language") or "").strip()

            print(f"DEBUG: Input values - user: {user_val}, story: {story_val}, product: {prod_val}, desc: {desc_val}, img: {img_val}, lang: {lang_val}")

            if user_val:
                os.environ["user"] = user_val
            if story_val:
                os.environ["user_story"] = story_val
            if prod_val:
                os.environ["product_name"] = prod_val
            if desc_val:
                os.environ["product_description"] = desc_val
            if img_val:
                # Copy image to web directory if it exists
                web_image_path = copy_image_to_web_dir(img_val)
                os.environ["image_path"] = web_image_path
                print(f"DEBUG: Image copied to web directory: {web_image_path}")
            else:
                print("DEBUG: No image_path provided")
            if lang_val:
                os.environ["language"] = lang_val

        # Instantiate after env is ready
        crew_instance = SocialMediaPromotion()
        crew_story_advertising = crew_instance.crew_story_advertising()

        result = crew_story_advertising.kickoff(inputs=inputs)
        print("✅ Story advertising workflow complete.\n")
        print(result)
        
        # Add product to website database
        if inputs:
            user_name = str(inputs.get("user") or inputs.get("user_name") or "").strip()
            product_name = str(inputs.get("product_name") or "").strip()
            product_details = str(inputs.get("product_description") or inputs.get("product_details") or "").strip()
            image_path = os.getenv("image_path", "")
            
            if user_name and product_name and product_details:
                add_product_to_website(user_name, product_name, product_details, image_path)
        
        return result
    except Exception as e:
        print(f"❌ Error in story advertising workflow: {str(e)}")
        raise e
    finally:
        # Don't clean up images for story advertising - they need to be preserved for posting
        pass

if __name__ == "__main__":
    print("🤖 Social Media Promotion System")
    print("Commands available:")
    print("1. 'run' - Execute promotion pipeline")
    print("2. 'train' - Run training iterations")
    print("3. 'replay <task_id>' - Replay specific task")
    print("4. 'exit' - Exit the program")
    
    while True:
        cmd = input("\nEnter command: ").strip().lower()
        
        if cmd == "run":
            run_promotion_pipeline()
        elif cmd == "train":
            iterations = int(input("Enter number of training iterations: "))
            filename = input("Enter output filename (default: training_results.json): ") or "training_results.json"
            run_training(iterations, filename)
        elif cmd.startswith("replay"):
            task_id = cmd.split(" ")[1] if len(cmd.split(" ")) > 1 else input("Enter task ID to replay: ")
            replay_task(task_id)
        elif cmd == "exit":
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid command. Try again.")
