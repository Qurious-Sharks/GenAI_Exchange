import os
import sys
from typing import Tuple
from pathlib import Path
from datetime import datetime
import gradio as gr
import requests

_PKG_DIR = Path(__file__).resolve().parent
_SRC_DIR = _PKG_DIR.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

try:
    from social_media_promotion.main import (
        run_promotion_pipeline,
        run_price_generation_pipeline,
        run_story_advertising_pipeline,
    )
    from social_media_promotion.tools.speech_tool import transcribe_speech
except ImportError:
    from main import (
        run_promotion_pipeline,
        run_price_generation_pipeline,
        run_story_advertising_pipeline,
    )
    from tools.speech_tool import transcribe_speech


try:
    import google.generativeai as genai # Gemini API
except Exception:
    genai = None

try:
    from google.cloud import translate_v2 as translate
    translate_client = translate.Client()
except Exception:
    translate_client = None

# --- Configuration and Setup ---
LANGUAGE_MAP = {
    "English": "en-US", "Hindi": "hi-IN", "Tamil": "ta-IN",
    "Telugu": "te-IN", "Malayalam": "ml-IN", "Urdu": "ur-IN"
}
IMAGES_DIR = Path(__file__).parent / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
AUDIOS_DIR = Path(__file__).parent / "audio"
AUDIOS_DIR.mkdir(parents=True, exist_ok=True)


# --- Helper Functions ---
def _save_file(temp_path: str, out_dir: Path, filename_prefix: str) -> str:
    """Saves a file from a temporary path to a permanent location with a timestamp."""
    if not temp_path or not os.path.exists(temp_path):
        return ""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    original_ext = os.path.splitext(temp_path)[1] or ".bin"
    filename = f"{filename_prefix}_{timestamp}{original_ext}"
    out_path = out_dir / filename
    
    # Ensure output directory exists
    out_dir.mkdir(parents=True, exist_ok=True)
    
    with open(temp_path, "rb") as f_in, open(out_path, "wb") as f_out:
        f_out.write(f_in.read())
    
    # For images, also copy to web uploads directory
    if original_ext.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
        try:
            from social_media_promotion.tools.img_tool import copy_image_to_web_dir
            web_path = copy_image_to_web_dir(str(out_path))
            return web_path if web_path else str(out_path)
        except Exception as e:
            print(f"Warning: Could not copy to web directory: {e}")
    
    return str(out_path)

def translate_text(text: str, target_language: str = "en") -> str:
    """Prefer Gemini, then Google Translate; fallback to original text."""
    if not text:
        return ""
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if genai and gemini_key:
        try:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = f"Translate the following text into {target_language}. Return only the translated text.\n\n{text}"
            resp = model.generate_content(prompt)
            out = (getattr(resp, "text", None) or "").strip()
            if out:
                return out
        except Exception:
            pass
    if translate_client:
        try:
            result = translate_client.translate(text, target_language=target_language)
            print(result)
            return result.get("translatedText", text)
        except Exception:
            return text
    return text

def transcribe_file_to_text(file_path: str, spoken_language_name: str) -> str:
    """Ensure mono PCM16 WAV before transcription to avoid channel errors, then transcribe."""
    if not file_path:
        return ""
    try:
        import soundfile as sf
        import numpy as np
        # Read with shape (num_samples,) or (num_samples, channels). Force 2D for simplicity.
        data, sr = sf.read(file_path, always_2d=True)
        # Mix down to mono
        mono = data.mean(axis=1)
        out_path = AUDIOS_DIR / f"mono_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
        sf.write(str(out_path), mono, sr, subtype='PCM_16')
        text = transcribe_speech(audio_file_path=str(out_path), language=spoken_language_name, translate_to_english=False)
        return text or ""
    except Exception as e:
        return f"Error transcribing audio: {e}"


# --- Tab 1: Full Promotion Handler ---
def full_promotion_ui(
    input_type: str, text_details: str, audio_file: str, audio_lang_name: str,
    translate_to_english: bool, user_name: str, product_name: str, cost: str, image_file: str,
    output_language: str,
) -> Tuple[str, str]:
    transcript = ""
    if input_type == "Audio":
        if not audio_file:
            return ("Please record your product details using the microphone.", "")
        raw = transcribe_file_to_text(audio_file, audio_lang_name)
        if raw.startswith("Error"):
            return (raw, "")
        transcript = translate_text(raw, "en") if translate_to_english else raw
    else:
        transcript = text_details or ""

    if not (user_name and product_name and transcript):
        return ("Please fill Your Name, Product Name and Product Details (text or audio).", transcript)

    image_path = _save_file(image_file, IMAGES_DIR, "promo_image")

    try:
        inputs = {
            "user_name": user_name.strip(), "user": user_name.strip(),
            "cost": int(cost) if cost and cost.isdigit() else 0,
            "product_name": product_name.strip(),
            "product_details": transcript.strip(), "product_description": transcript.strip(),
            "product_image_path": image_path, "image_path": image_path,
            "language": output_language,
        }
        result = run_promotion_pipeline(inputs=inputs)
        output = getattr(result, 'raw', str(result))
        # Also send to shopping backend if available
        try:
            _ = requests.post("http://127.0.0.1:8010/api/products", json={
                "user": user_name.strip(),
                "product_name": product_name.strip(),
                "product_details": transcript.strip(),
                "price": str(inputs.get("cost", "")),
                "image_path": image_path or "",
            }, timeout=2)
        except Exception:
            pass
        return (output, transcript)
    except Exception as e:
        return (f"Error while running promotion: {e}", transcript)


# --- Tab 2: Price Analysis Handler ---
def price_ui(
    input_type: str, text_details: str, audio_file: str, audio_lang_name: str,
    translate_to_english: bool, user_name: str, product_name: str,
    output_language: str,
) -> Tuple[str, str]:
    transcript = ""
    if input_type == "Audio":
        if not audio_file:
            return ("Please record your product details using the microphone.", "")
        raw = transcribe_file_to_text(audio_file, audio_lang_name)
        if raw.startswith("Error"):
            return (raw, "")
        transcript = translate_text(raw, "en") if translate_to_english else raw
    else:
        transcript = text_details or ""

    if not (user_name and product_name and transcript):
        return ("Please fill Your Name, Product Name and Product Details (text or audio).", transcript)

    try:
        inputs = {
            "user_name": user_name.strip(), "user": user_name.strip(),
            "product_name": product_name.strip(),
            "product_details": transcript.strip(), "product_description": transcript.strip(),
            "language": output_language,
        }
        result = run_price_generation_pipeline(inputs=inputs)
        output = getattr(result, 'raw', str(result))
        return (output, transcript)
    except Exception as e:
        return (f"Error while running price analysis: {e}", transcript)


# --- Tab 3: Story Advertising Handler ---
def story_ui(
    prod_input_type: str, prod_text: str, prod_audio: str, prod_audio_lang_name: str,
    story_input_type: str, story_text: str, story_audio: str, story_audio_lang_name: str,
    translate_to_english: bool, user_name: str, product_name: str, image_file: str,
    output_language: str,
) -> Tuple[str, str, str]:
    prod_details = ""
    if prod_input_type == "Audio":
        if not prod_audio:
            return ("Please record the product audio.", "", "")
        raw = transcribe_file_to_text(prod_audio, prod_audio_lang_name)
        if raw.startswith("Error"):
            return (raw, "", "")
        prod_details = translate_text(raw, "en") if translate_to_english else raw
    else:
        prod_details = prod_text or ""

    story = ""
    if story_input_type == "Audio":
        if not story_audio:
            return ("Please record the story audio.", "", "")
        raw = transcribe_file_to_text(story_audio, story_audio_lang_name)
        if raw.startswith("Error"):
            return (raw, "", "")
        story = translate_text(raw, "en") if translate_to_english else raw
    else:
        story = story_text or ""

    if not (user_name and product_name and prod_details and story):
        return ("Please fill Your Name, Product Name, Product Details and Your Story.", prod_details, story)
    
    image_path = _save_file(image_file, IMAGES_DIR, "story_image")

    try:
        inputs = {
            "user_name": user_name.strip(), "user": user_name.strip(),
            "user_story": story.strip(),
            "product_name": product_name.strip(),
            "product_details": prod_details.strip(), "product_description": prod_details.strip(),
            "product_image_path": image_path, "image_path": image_path,
            "language": output_language,
        }
        result = run_story_advertising_pipeline(inputs=inputs)
        output = getattr(result, 'raw', str(result))
        return (output, prod_details, story)
    except Exception as e:
        return (f"Error while running story advertising: {e}", prod_details, story)


# --- Build Gradio Interface ---
def build_demo():
    with gr.Blocks(title="Social Media Promotion", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# 📣 Social Media Promotion (Gradio)")

        with gr.Tab("Full Promotion"):
            with gr.Row():
                user_name = gr.Textbox(label="Your Name")
                product_name = gr.Textbox(label="Product Name")
                cost = gr.Textbox(label="Product Cost (numeric)")
            image_file = gr.Image(type="filepath", label="Product Image (optional) but our ads are better when images are uploaded") # IMAGE UPLOAD ADDED
            with gr.Row():
                input_type = gr.Radio(["Text", "Audio"], value="Text", label="Input Type for Product Details")
                translate_chk = gr.Checkbox(value=True, label="Translate to English")
            text_details = gr.Textbox(label="Product Details (Type here)", visible=True)
            with gr.Column(visible=False) as audio_column:
                audio_file = gr.Audio(type="filepath", label="Record Audio", interactive=True) # RECORD ONLY
                audio_lang = gr.Dropdown(list(LANGUAGE_MAP.keys()), value="English", label="Spoken Language")
            
            output_language = gr.Dropdown(["English", "Hindi", "Tamil", "Telugu", "Malayalam", "Urdu"], value="English", label="Output Language")
            submit_btn = gr.Button("Generate Full Promotion", variant="primary")
            out_md = gr.Markdown()
            transcript_preview = gr.Textbox(label="Transcript Used", interactive=False)

            def _toggle_main(io_choice: str):
                is_audio = io_choice == "Audio"
                return gr.update(visible=not is_audio), gr.update(visible=is_audio)
            input_type.change(_toggle_main, inputs=[input_type], outputs=[text_details, audio_column])
            submit_btn.click(full_promotion_ui, 
                inputs=[input_type, text_details, audio_file, audio_lang, translate_chk, user_name, product_name, cost, image_file, output_language], 
                outputs=[out_md, transcript_preview])

        with gr.Tab("Know Your Price"):
            with gr.Row():
                p_user_name = gr.Textbox(label="Your Name")
                p_product_name = gr.Textbox(label="Product Name")
            with gr.Row():
                p_input_type = gr.Radio(["Text", "Audio"], value="Text", label="Input Type for Product Details")
                p_translate_chk = gr.Checkbox(value=True, label="Translate to English")
            p_text_details = gr.Textbox(label="Product Details (Type here)", visible=True)
            with gr.Column(visible=False) as p_audio_column:
                p_audio_file = gr.Audio(type="filepath", label="Record Audio", interactive=True) # RECORD ONLY
                p_audio_lang = gr.Dropdown(list(LANGUAGE_MAP.keys()), value="English", label="Spoken Language")

            output_language_p = gr.Dropdown(["English", "Hindi", "Tamil", "Telugu", "Malayalam", "Urdu"], value="English", label="Output Language")
            p_submit_btn = gr.Button("Get Price Analysis", variant="primary")
            p_out_md = gr.Markdown()
            p_transcript_preview = gr.Textbox(label="Transcript Used", interactive=False)

            def _toggle_price(io_choice: str):
                is_audio = io_choice == "Audio"
                return gr.update(visible=not is_audio), gr.update(visible=is_audio)
            p_input_type.change(_toggle_price, inputs=[p_input_type], outputs=[p_text_details, p_audio_column])
            p_submit_btn.click(price_ui, 
                inputs=[p_input_type, p_text_details, p_audio_file, p_audio_lang, p_translate_chk, p_user_name, p_product_name, output_language_p], 
                outputs=[p_out_md, p_transcript_preview])

        with gr.Tab("Advertise Your Story"):
            with gr.Row():
                s_user_name = gr.Textbox(label="Your Name")
                s_product_name = gr.Textbox(label="Product Name")
            s_image_file = gr.Image(type="filepath", label="Picture with your craft(not optional)") # IMAGE UPLOAD ADDED
            s_translate_chk = gr.Checkbox(value=True, label="Translate all audio to English")
            
            gr.Markdown("### Product Details")
            s_prod_input_type = gr.Radio(["Text", "Audio"], value="Text", label="Product Details Input Type")
            s_prod_text = gr.Textbox(label="Product Details (Type here)", visible=True)
            with gr.Column(visible=False) as s_prod_audio_col:
                s_prod_audio = gr.Audio(type="filepath", label="Record Audio", interactive=True) # RECORD ONLY
                s_prod_lang = gr.Dropdown(list(LANGUAGE_MAP.keys()), value="English", label="Spoken Language (Product)")
            
            gr.Markdown("### Your Story")
            s_story_input_type = gr.Radio(["Text", "Audio"], value="Text", label="Your Story Input Type")
            s_story_text = gr.Textbox(label="Your Story (Type here)", visible=True)
            with gr.Column(visible=False) as s_story_audio_col:
                s_story_audio = gr.Audio(type="filepath", label="Record Audio", interactive=True) # RECORD ONLY
                s_story_lang = gr.Dropdown(list(LANGUAGE_MAP.keys()), value="English", label="Spoken Language (Story)")

            output_language_s = gr.Dropdown(["English", "Hindi", "Tamil", "Telugu", "Malayalam", "Urdu"], value="English", label="Output Language")
            s_submit_btn = gr.Button("Create & Publish Story", variant="primary")
            s_out_md = gr.Markdown()
            s_prod_preview = gr.Textbox(label="Product Transcript Used", interactive=False)
            s_story_preview = gr.Textbox(label="Story Transcript Used", interactive=False)

            def _toggle_story_prod(io_choice: str):
                is_audio = io_choice == "Audio"
                return gr.update(visible=not is_audio), gr.update(visible=is_audio)
            s_prod_input_type.change(_toggle_story_prod, inputs=[s_prod_input_type], outputs=[s_prod_text, s_prod_audio_col])

            def _toggle_story_user(io_choice: str):
                is_audio = io_choice == "Audio"
                return gr.update(visible=not is_audio), gr.update(visible=is_audio)
            s_story_input_type.change(_toggle_story_user, inputs=[s_story_input_type], outputs=[s_story_text, s_story_audio_col])
            
            s_submit_btn.click(story_ui, 
                inputs=[
                    s_prod_input_type, s_prod_text, s_prod_audio, s_prod_lang,
                    s_story_input_type, s_story_text, s_story_audio, s_story_lang,
                    s_translate_chk, s_user_name, s_product_name, s_image_file,
                    output_language_s
                ], 
                outputs=[s_out_md, s_prod_preview, s_story_preview])

    return demo

if __name__ == "__main__":
    demo = build_demo()
    demo.launch(share=True, server_name="0.0.0.0")