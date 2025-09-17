import os
from pathlib import Path
from datetime import datetime
import streamlit as st
from streamlit_mic_recorder import mic_recorder
from social_media_promotion.main import run_promotion_pipeline, run_price_generation_pipeline, run_story_advertising_pipeline
from social_media_promotion.tools.speech_tool import transcribe_speech

# --- Directory Setup ---
IMAGES_DIR = Path(__file__).parent / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
AUDIOS_DIR = Path(__file__).parent / "audio"
AUDIOS_DIR.mkdir(parents=True, exist_ok=True)

# --- Helper Functions ---
def save_uploaded_image(uploaded_file) -> str:
    if uploaded_file is None:
        return ""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = uploaded_file.name.replace(" ", "_")
    filename = f"{timestamp}_{safe_name}"
    out_path = IMAGES_DIR / filename
    with open(out_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    print(f"DEBUG: Image saved to: {str(out_path)}")
    return str(out_path)

def save_uploaded_audio(audio_obj, default_name: str = "audio_note.wav") -> str:
    if audio_obj is None:
        return ""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = getattr(audio_obj, 'name', None) or default_name
    safe_name = str(name).replace(" ", "_")
    filename = f"{timestamp}_{safe_name}"
    out_path = AUDIOS_DIR / filename
    data_bytes = None

    # Handle mic_recorder output which is a dictionary
    if isinstance(audio_obj, dict) and 'bytes' in audio_obj:
        data_bytes = audio_obj['bytes']
    # Handle UploadedFile object
    elif hasattr(audio_obj, 'getbuffer'):
        data_bytes = audio_obj.getbuffer()
    # Handle other potential byte-like objects
    elif hasattr(audio_obj, 'read'):
        data_bytes = audio_obj.read()
    elif isinstance(audio_obj, (bytes, bytearray)):
        data_bytes = audio_obj
    else:
        getvalue = getattr(audio_obj, 'getvalue', None)
        if callable(getvalue):
            data_bytes = getvalue()

    if data_bytes is None:
        return ""
    with open(out_path, "wb") as f:
        f.write(data_bytes)
    print(f"DEBUG: Audio saved to: {str(out_path)}")
    return str(out_path)

# --- Backend Functions ---
def _run_backend(user_name: str, product_name: str, cost: int, product_image_path: str, product_details: str, language: str):
    inputs = {
        "user_name": user_name, "user": user_name, "cost": cost,
        "product_name": product_name, "product_image_path": product_image_path,
        "image_path": product_image_path, "product_details": product_details,
        "product_description": product_details, "language": language,
    }
    return run_promotion_pipeline(inputs=inputs)

def _run_price_backend(user_name: str, product_name: str, product_details: str, language: str):
    inputs = {
        "user_name": user_name, "user": user_name, "product_name": product_name,
        "product_details": product_details, "product_description": product_details,
        "language": language,
    }
    return run_price_generation_pipeline(inputs=inputs)

def _run_story_backend(user_name: str, user_story: str, product_name: str, product_details: str, product_image_path: str, language: str):
    inputs = {
        "user_name": user_name, "user": user_name, "user_story": user_story,
        "product_name": product_name, "product_details": product_details,
        "product_description": product_details, "product_image_path": product_image_path,
        "image_path": product_image_path, "language": language,
    }
    return run_story_advertising_pipeline(inputs=inputs)

# --- Main Streamlit App ---
def main():
    st.set_page_config(page_title="Social Media Promotion", page_icon="📣", layout="centered")
    st.title("📣 Social Media Promotion")
    st.caption("Choose your promotion strategy from the tabs below.")

    tab1, tab2, tab3 = st.tabs(["🎯 Full Promotion", "💰 Know Your Price", "📖 Advertise Your Story"])

    with tab1:
        st.subheader("🎯 Full Social Media Promotion")
        st.caption("Complete promotion workflow with image/video generation and Telegram publishing.")
        
        with st.form("promotion_form", clear_on_submit=False):
            user_name = st.text_input("Your Name", placeholder="e.g. Jane Doe")
            product_name = st.text_input("Product Name", placeholder="e.g. Smart Hydration Bottle")
            cost = st.text_input("Product Cost", placeholder="e.g. 50rs etc.")
            product_details = st.text_area("Product Details", placeholder="Describe features, audience, tone, platforms, etc.", height=160)
            language = st.selectbox("Language", ["English", "Hindi", "Tamil", "Telugu", "Spanish"], index=0)
            uploaded_image = st.file_uploader("Product Image (optional)", type=["png", "jpg", "jpeg", "webp"], key="promo_image")
            input_mode = st.radio("Input Mode", ["Text", "Audio"], horizontal=True, key="promo_mode")
            
            audio_bytes = None
            audio_note_upload = None
            if input_mode == "Audio":
                st.caption("Record with your mic or upload an audio file.")
                audio_bytes = mic_recorder(start_prompt="⏺️ Start recording", stop_prompt="⏹️ Stop recording", just_once=True, key='promo_recorder')
                audio_note_upload = st.file_uploader("Or upload audio", type=["wav", "mp3", "m4a", "flac"], key="promo_audio")
            
            submitted = st.form_submit_button("Generate Full Promotion")

        if submitted:
            resolved_details = product_details
            if st.session_state.get("promo_mode") == "Audio":
                chosen_audio = audio_bytes or audio_note_upload
                if not chosen_audio:
                    st.error("Please record or upload an audio note.")
                    return
                audio_path = save_uploaded_audio(chosen_audio)
                with st.spinner("Transcribing audio..."):
                    resolved_details = transcribe_speech(audio_file_path=audio_path, language=language, translate_to_english=True)
                if not resolved_details or resolved_details.startswith("Error"):
                    st.error(resolved_details or "Transcription failed.")
                    return
            
            product_image_path = save_uploaded_image(uploaded_image) if uploaded_image else ""

            if not user_name or not product_name or not resolved_details:
                st.error("Please provide Your Name, Product Name, and details (text or audio).")
            else:
                with st.spinner("Generating promotion assets..."):
                    try:
                        result = _run_backend(
                            user_name=user_name.strip(),
                            product_name=product_name.strip(),
                            cost=int(cost) if cost.isdigit() else 0,
                            product_image_path=product_image_path,
                            product_details=resolved_details.strip(),
                            language=language,
                        )
                        st.success("Done!")
                        if isinstance(result, str):
                            st.subheader("Output")
                            st.markdown(result)
                        elif hasattr(result, "raw") and isinstance(result.raw, str):
                            st.subheader("Output")
                            st.markdown(result.raw)
                        else:
                            st.subheader("Output (serialized)")
                            st.json(result)
                    except Exception as e:
                        st.error(f"Error while running the pipeline: {e}")

    with tab2:
        st.subheader("💰 Know Your Price")
        st.caption("Get optimal pricing recommendations based on market research.")
        
        with st.form("price_form", clear_on_submit=False):
            user_name_price = st.text_input("Your Name", placeholder="e.g. Jane Doe", key="price_user")
            product_name_price = st.text_input("Product Name", placeholder="e.g. Smart Hydration Bottle", key="price_product")
            product_details_price = st.text_area("Product Details", placeholder="Describe features, target market, unique selling points, etc.", height=160, key="price_details")
            language_price = st.selectbox("Language", ["English", "Hindi", "Tamil", "Telugu", "Spanish"], index=0, key="price_lang")
            input_mode_price = st.radio("Input Mode", ["Text", "Audio"], horizontal=True, key="price_mode")
            
            audio_bytes_price = None
            audio_price_upload = None
            if input_mode_price == "Audio":
                st.caption("Record with your mic or upload an audio file.")
                audio_bytes_price = mic_recorder(start_prompt="⏺️ Start recording", stop_prompt="⏹️ Stop recording", just_once=True, key='price_recorder')
                audio_price_upload = st.file_uploader("Or upload audio", type=["wav", "mp3", "m4a", "flac"], key="price_audio")
            
            submitted_price = st.form_submit_button("Get Price Analysis")

        if submitted_price:
            resolved_details_price = product_details_price
            if st.session_state.get("price_mode") == "Audio":
                chosen_audio = audio_bytes_price or audio_price_upload
                if not chosen_audio:
                    st.error("Please record or upload an audio note.")
                    return
                audio_path = save_uploaded_audio(chosen_audio)
                with st.spinner("Transcribing audio..."):
                    resolved_details_price = transcribe_speech(audio_file_path=audio_path, language=language_price, translate_to_english=True)
                if not resolved_details_price or resolved_details_price.startswith("Error"):
                    st.error(resolved_details_price or "Transcription failed.")
                    return

            if not user_name_price or not product_name_price or not resolved_details_price:
                st.error("Please provide Your Name, Product Name, and details (text or audio).")
            else:
                with st.spinner("Analyzing market prices..."):
                    try:
                        result = _run_price_backend(
                            user_name=user_name_price.strip(),
                            product_name=product_name_price.strip(),
                            product_details=resolved_details_price.strip(),
                            language=language_price,
                        )
                        st.success("Price analysis complete!")
                        if isinstance(result, str):
                            st.subheader("Price Analysis")
                            st.markdown(result)
                        elif hasattr(result, "raw") and isinstance(result.raw, str):
                            st.subheader("Price Analysis")
                            st.markdown(result.raw)
                        else:
                            st.subheader("Price Analysis (serialized)")
                            st.json(result)
                    except Exception as e:
                        st.error(f"Error while running price analysis: {e}")

    with tab3:
        st.subheader("📖 Advertise Your Story")
        st.caption("Create emotional stories and publish to Telegram channels and stories.")
        
        with st.form("story_form", clear_on_submit=False):
            user_name_story = st.text_input("Your Name", placeholder="e.g. Jane Doe", key="story_user")
            product_name_story = st.text_input("Product Name", placeholder="e.g. Handmade Pottery", key="story_product")
            product_details_story = st.text_area("Product Details", placeholder="Describe your product features, benefits, and what makes it special...", height=120, key="story_product_details")
            user_story = st.text_area("Your Story", placeholder="Tell us about your journey, challenges, and passion for your craft...", height=160, key="story_content")
            language_story = st.selectbox("Language", ["English", "Hindi", "Tamil", "Telugu", "Malayalam"], index=0, key="story_lang")
            uploaded_image_story = st.file_uploader("Picture with your craft (optional)", type=["png", "jpg", "jpeg", "webp"], key="story_image")
            input_mode_story = st.radio("Input Mode", ["Text", "Audio"], horizontal=True, key="story_mode")
            
            audio_bytes_story = None
            audio_story_upload = None
            if input_mode_story == "Audio":
                st.caption("Record your story with your mic or upload an audio file.")
                audio_bytes_story = mic_recorder(start_prompt="⏺️ Start recording", stop_prompt="⏹️ Stop recording", just_once=True, key='story_recorder')
                audio_story_upload = st.file_uploader("Or upload audio", type=["wav", "mp3", "m4a", "flac"], key="story_audio")
            
            submitted_story = st.form_submit_button("Create & Publish Story")

        if submitted_story:
            resolved_story = user_story
            if st.session_state.get("story_mode") == "Audio":
                chosen_audio = audio_bytes_story or audio_story_upload
                if not chosen_audio:
                    st.error("Please record or upload an audio note.")
                    return
                audio_path = save_uploaded_audio(chosen_audio)
                with st.spinner("Transcribing audio..."):
                    resolved_story = transcribe_speech(audio_file_path=audio_path, language=language_story, translate_to_english=True)
                if not resolved_story or resolved_story.startswith("Error"):
                    st.error(resolved_story or "Transcription failed.")
                    return
            
            product_image_path_story = save_uploaded_image(uploaded_image_story) if uploaded_image_story else ""
            
            if not user_name_story or not product_name_story or not product_details_story or not resolved_story:
                st.error("Please provide Your Name, Product Name, Product Details, and Story (text or audio).")
            else:
                with st.spinner("Creating emotional story and publishing..."):
                    try:
                        result = _run_story_backend(
                            user_name=user_name_story.strip(),
                            user_story=resolved_story.strip(),
                            product_name=product_name_story.strip(),
                            product_details=product_details_story.strip(),
                            product_image_path=product_image_path_story,
                            language=language_story,
                        )
                        st.success("Story created and published!")
                        if isinstance(result, str):
                            st.subheader("Story Output")
                            st.markdown(result)
                        elif hasattr(result, "raw") and isinstance(result.raw, str):
                            st.subheader("Story Output")
                            st.markdown(result.raw)
                        else:
                            st.subheader("Story Output (serialized)")
                            st.json(result)
                    except Exception as e:
                        st.error(f"Error while running story advertising: {e}")

if __name__ == "__main__":
    main()