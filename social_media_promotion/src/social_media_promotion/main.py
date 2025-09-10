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
        # Resolve placeholders via env for YAML {vars}
        if inputs:
            user_val = str(inputs.get("user") or inputs.get("user_name") or "").strip()
            prod_val = str(inputs.get("product_name") or "").strip()
            desc_val = str(inputs.get("product_description") or inputs.get("product_details") or "").strip()
            img_val = str(inputs.get("image_path") or inputs.get("product_image_path") or "").strip()

            if user_val:
                os.environ["user"] = user_val
            if prod_val:
                os.environ["product_name"] = prod_val
            if desc_val:
                os.environ["product_description"] = desc_val
            if img_val:
                os.environ["image_path"] = img_val

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
        # Cleanup generated media per request
        base_dir = Path(os.path.dirname(__file__))
        for folder in [base_dir / "images", base_dir / "videos"]:
            if folder.exists() and folder.is_dir():
                for child in folder.glob("*"):
                    try:
                        if child.is_file():
                            child.unlink(missing_ok=True)
                        elif child.is_dir():
                            shutil.rmtree(child, ignore_errors=True)
                    except Exception:
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
