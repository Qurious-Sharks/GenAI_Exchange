import os
import sys
import unittest
import tempfile
from unittest import mock
from pathlib import Path

# Ensure src/ is on sys.path so we can import the package without installation
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from social_media_promotion.tools.custom_tool import VeoVideoGenerator  # noqa: E402


class TestVeoVideoGenerator(unittest.TestCase):
    def setUp(self):
        # Provide a fake API key for the genai client
        self.env_patcher = mock.patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False)
        self.env_patcher.start()

        # Temporary output directory for videos
        self.tmpdir = tempfile.TemporaryDirectory()
        self.output_dir = self.tmpdir.name
        self.env_outdir = mock.patch.dict(os.environ, {"VEO_OUTPUT_DIR": self.output_dir}, clear=False)
        self.env_outdir.start()

    def tearDown(self):
        self.env_patcher.stop()
        self.env_outdir.stop()
        self.tmpdir.cleanup()

    @mock.patch("social_media_promotion.tools.custom_tool.genai.Client")
    def test_run_with_image_path_uses_uploaded_image(self, mock_client_cls):
        # Arrange: create a dummy image file
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmpimg:
            tmpimg_path = tmpimg.name

        # Build a fake client
        mock_client = mock.Mock()
        mock_client_cls.return_value = mock_client

        # files.upload returns an uploaded file handle object
        uploaded_image = object()
        mock_client.files.upload.return_value = uploaded_image

        # generate_videos returns an operation that completes after one poll
        class FakeOperation:
            def __init__(self):
                self.done = False
                self.response = None

        op = FakeOperation()

        def fake_operations_get(_op):
            _op.done = True
            video_obj = type("VideoObj", (), {"video": "file_123"})
            _op.response = type("Response", (), {"generated_videos": [video_obj]})
            return _op

        mock_client.models.generate_videos.return_value = op
        mock_client.operations.get.side_effect = fake_operations_get

        # files.download returns an object with a save() method
        class DownloadObj:
            def save(self, path):
                with open(path, "wb") as f:
                    f.write(b"test-bytes")

        mock_client.files.download.return_value = DownloadObj()

        tool = VeoVideoGenerator()

        # Act
        try:
            out_path = tool._run(
                prompt="Test prompt",
                duration=10,
                style="social media",
                image_path=tmpimg_path,
                aspect_ratio="9:16",
            )
        finally:
            try:
                os.remove(tmpimg_path)
            except OSError:
                pass

        # Assert
        mock_client.files.upload.assert_called_once_with(file=tmpimg_path)
        mock_client.models.generate_images.assert_not_called()
        self.assertTrue(Path(out_path).exists())
        self.assertTrue(out_path.endswith(".mp4"))

    @mock.patch("social_media_promotion.tools.custom_tool.genai.Client")
    def test_run_without_image_generates_imagen_first(self, mock_client_cls):
        # Arrange: fake client
        mock_client = mock.Mock()
        mock_client_cls.return_value = mock_client

        # Imagen response stub
        gen_img = type("Img", (), {"image": "image_ref"})
        imagen_resp = type("ImagenResp", (), {"generated_images": [gen_img]})
        mock_client.models.generate_images.return_value = imagen_resp

        # generate_videos returns an operation that completes after one poll
        class FakeOperation:
            def __init__(self):
                self.done = False
                self.response = None

        op = FakeOperation()

        def fake_operations_get(_op):
            _op.done = True
            video_obj = type("VideoObj", (), {"video": "file_987"})
            _op.response = type("Response", (), {"generated_videos": [video_obj]})
            return _op

        mock_client.models.generate_videos.return_value = op
        mock_client.operations.get.side_effect = fake_operations_get

        # files.download returns an object with raw content
        download_obj = type("DownloadObj", (), {"content": b"video-bytes"})
        mock_client.files.download.return_value = download_obj()

        tool = VeoVideoGenerator()

        # Act
        out_path = tool._run(
            prompt="Test prompt no image",
            duration=12,
            style="story",
            image_path=None,
            aspect_ratio="16:9",
        )

        # Assert
        mock_client.models.generate_images.assert_called_once()
        self.assertTrue(Path(out_path).exists())
        self.assertTrue(out_path.endswith(".mp4"))


if __name__ == "__main__":
    unittest.main()


