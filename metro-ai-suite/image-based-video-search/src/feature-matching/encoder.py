import base64
import io

from PIL import Image


class Base64ImageProcessor:
    def __init__(self, size=(224, 224)):
        """
        Initialize the processor with the desired output size.
        Args:
            size (tuple): The target size for resizing (width, height).
        """
        self.size = size

    def process_image_to_base64(self, image: Image):
        """
        Preprocesses the image (resize, etc.) and converts it to a Base64 string.

        Args:
            image (PIL.Image): The input image.

        Returns:
            str: The Base64-encoded representation of the processed image.
        """
        # Step 1: Convert the image to RGB (if it's not already)
        image = image.convert("RGB")

        # Step 2: Resize the image to the desired size
        image = image.resize(self.size, Image.LANCZOS)

        # Step 3: Save the image to a BytesIO buffer
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        buffered.seek(0)

        # Step 4: Encode the image bytes to a Base64 string
        base64_string = base64.b64encode(buffered.read()).decode("utf-8")

        return base64_string
