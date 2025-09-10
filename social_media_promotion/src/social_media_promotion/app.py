import os
from pathlib import Path
from datetime import datetime
import streamlit as st
from social_media_promotion.main import run_promotion_pipeline

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
    return str(out_path)

def _run_backend(user_name: str, product_name: str, product_image_path: str, product_details: str):
    inputs = {
        "user_name": user_name,
        "user": user_name,
        "product_name": product_name,
        "product_image_path": product_image_path,
        "image_path": product_image_path,
        "product_details": product_details,
        "product_description": product_details,
    }
    return run_promotion_pipeline(inputs=inputs)

def main():
    st.set_page_config(page_title="Social Media Promotion", page_icon="📣", layout="centered")
    st.title("📣 Social Media Promotion")
    st.caption("Enter details to generate your promotion artifacts.")

    with st.form("promotion_form", clear_on_submit=False):
        user_name = st.text_input("Your Name", placeholder="e.g. Jane Doe")
        product_name = st.text_input("Product Name", placeholder="e.g. Smart Hydration Bottle")
        product_details = st.text_area(
            "Product Details",
            placeholder="Describe features, audience, tone, platforms, etc.",
            height=160,
        )
        uploaded_image = st.file_uploader("Product Image (optional)", type=["png", "jpg", "jpeg", "webp"])
        submitted = st.form_submit_button("Generate")

    if submitted:
        if not user_name or not product_name or not product_details:
            st.error("Please fill in Your Name, Product Name, and Product Details.")
            return

        product_image_path = ""
        if uploaded_image is not None:
            product_image_path = save_uploaded_image(uploaded_image)

        with st.spinner("Generating promotion assets..."):
            try:
                result = _run_backend(
                    user_name=user_name.strip(),
                    product_name=product_name.strip(),
                    product_image_path=product_image_path,
                    product_details=product_details.strip(),
                )
            except Exception as e:
                st.error(f"Error while running the pipeline: {e}")
                return

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

if __name__ == "__main__":
    main()