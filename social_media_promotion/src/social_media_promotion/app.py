import os
from pathlib import Path
from datetime import datetime
import streamlit as st
from social_media_promotion.main import run_promotion_pipeline, run_price_generation_pipeline, run_story_advertising_pipeline

IMAGES_DIR = Path(__file__).parent / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

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

def _run_backend(user_name: str, product_name: str, cost: int, product_image_path: str, product_details: str, language: str):
    inputs = {
        "user_name": user_name,
        "user": user_name,
        "cost": cost,
        "product_name": product_name,
        "product_image_path": product_image_path,
        "image_path": product_image_path,
        "product_details": product_details,
        "product_description": product_details,
        "language": language,
    }
    return run_promotion_pipeline(inputs=inputs)

def _run_price_backend(user_name: str, product_name: str, product_details: str, language: str):
    inputs = {
        "user_name": user_name,
        "user": user_name,
        "product_name": product_name,
        "product_details": product_details,
        "product_description": product_details,
        "language": language,
    }
    return run_price_generation_pipeline(inputs=inputs)

def _run_story_backend(user_name: str, user_story: str, product_name: str, product_details: str, product_image_path: str, language: str):
    inputs = {
        "user_name": user_name,
        "user": user_name,
        "user_story": user_story,
        "product_name": product_name,
        "product_details": product_details,
        "product_description": product_details,
        "product_image_path": product_image_path,
        "image_path": product_image_path,
        "language": language,
    }
    return run_story_advertising_pipeline(inputs=inputs)

def main():
    st.set_page_config(page_title="Social Media Promotion", page_icon="📣", layout="centered")
    st.title("📣 Social Media Promotion")
    st.caption("Choose your promotion strategy from the tabs below.")

    # Create tabs
    tab1, tab2, tab3 = st.tabs(["🎯 Full Promotion", "💰 Know Your Price", "📖 Advertise Your Story"])

    with tab1:
        st.subheader("🎯 Full Social Media Promotion")
        st.caption("Complete promotion workflow with image/video generation and Telegram publishing.")
        
        with st.form("promotion_form", clear_on_submit=False):
            user_name = st.text_input("Your Name", placeholder="e.g. Jane Doe")
            product_name = st.text_input("Product Name", placeholder="e.g. Smart Hydration Bottle")
            cost = st.text_input("Product Cost", placeholder="e.g. 50rs etc.")
            product_details = st.text_area(
                "Product Details",
                placeholder="Describe features, audience, tone, platforms, etc.",
                height=160,
            )
            language = st.selectbox("Language", ["English", "Hindi", "Tamil", "Telugu", "Spanish"], index=0)
            uploaded_image = st.file_uploader("Product Image (optional)", type=["png", "jpg", "jpeg", "webp"])
            submitted = st.form_submit_button("Generate Full Promotion")

        if submitted:
            if not user_name or not product_name or not product_details:
                st.error("Please fill in Your Name, Product Name, and Product Details.")
            else:
                product_image_path = ""
                if uploaded_image is not None:
                    product_image_path = save_uploaded_image(uploaded_image)

                with st.spinner("Generating promotion assets..."):
                    try:
                        result = _run_backend(
                            user_name=user_name.strip(),
                            product_name=product_name.strip(),
                            cost = int(cost) if cost.isdigit() else 0,
                            product_image_path=product_image_path,
                            product_details=product_details.strip(),
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
            product_details_price = st.text_area(
                "Product Details",
                placeholder="Describe features, target market, unique selling points, etc.",
                height=160,
                key="price_details"
            )
            language_price = st.selectbox("Language", ["English", "Hindi", "Tamil", "Telugu", "Spanish"], index=0, key="price_lang")
            submitted_price = st.form_submit_button("Get Price Analysis")

        if submitted_price:
            if not user_name_price or not product_name_price or not product_details_price:
                st.error("Please fill in Your Name, Product Name, and Product Details.")
            else:
                with st.spinner("Analyzing market prices..."):
                    try:
                        result = _run_price_backend(
                            user_name=user_name_price.strip(),
                            product_name=product_name_price.strip(),
                            product_details=product_details_price.strip(),
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
            product_details_story = st.text_area(
                "Product Details",
                placeholder="Describe your product features, benefits, and what makes it special...",
                height=120,
                key="story_product_details"
            )
            user_story = st.text_area(
                "Your Story",
                placeholder="Tell us about your journey, challenges, and passion for your craft...",
                height=160,
                key="story_content"
            )
            language_story = st.selectbox("Language", ["English", "Hindi", "Tamil", "Telugu", "Spanish"], index=0, key="story_lang")
            uploaded_image_story = st.file_uploader("Picture with your craft (optional)", type=["png", "jpg", "jpeg", "webp"], key="story_image")
            submitted_story = st.form_submit_button("Create & Publish Story")

        if submitted_story:
            if not user_name_story or not user_story or not product_name_story or not product_details_story:
                st.error("Please fill in Your Name, Product Name, Product Details, and Your Story.")
            else:
                product_image_path_story = ""
                if uploaded_image_story is not None:
                    product_image_path_story = save_uploaded_image(uploaded_image_story)
                    print(f"DEBUG: Story image path: {product_image_path_story}")

                with st.spinner("Creating emotional story and publishing..."):
                    try:
                        result = _run_story_backend(
                            user_name=user_name_story.strip(),
                            user_story=user_story.strip(),
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