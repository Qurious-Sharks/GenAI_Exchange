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

def assign_output_files():
    """Ensure output directory exists and any output file paths are set up."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

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
                os.environ["image_path"] = img_val
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
        return result
    except Exception as e:
        print(f"❌ Error in workflow: {str(e)}")
        raise e
    finally:
        base_dir = Path(os.path.dirname(__file__))
        images_folder = base_dir / "images"
        if images_folder.exists() and images_folder.is_dir():
            for child in images_folder.glob("*"):
                try:
                    if child.is_file():
                        child.unlink(missing_ok=True)
                    elif child.is_dir():
                        shutil.rmtree(child, ignore_errors=True)
                except Exception:
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
                os.environ["image_path"] = img_val
                print(f"DEBUG: Setting image_path to: {img_val}")
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
