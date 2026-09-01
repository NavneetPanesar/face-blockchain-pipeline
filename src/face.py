import io
import cv2
import numpy as np
from PIL import Image
from deepface import DeepFace


class FaceDetector:
    MODEL   = "Facenet"   # 128-dim embedding
    BACKEND = "opencv"    # fast and reliable

    def detect_and_encode(self, image_path: str) -> dict:
        """
        Detect the first face in image_path.
        Returns a dict with embedding, face_bytes (JPEG), cropped_path, region.
        Raises ValueError if no face is found.
        """
        results = DeepFace.represent(
            img_path=image_path,
            model_name=self.MODEL,
            enforce_detection=True,
            detector_backend=self.BACKEND,
            align=True,
        )

        if not results:
            raise ValueError("No face detected in the input image.")

        best      = results[0]
        embedding = best["embedding"]        # list of 128 floats
        region    = best["facial_area"]      # {x, y, w, h}

        # Crop face from original image with padding
        img_bgr = cv2.imread(image_path)
        if img_bgr is None:
            raise ValueError(f"Cannot read image file: {image_path}")
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        h, w    = img_rgb.shape[:2]

        pad = 40
        x1 = max(0, region["x"] - pad)
        y1 = max(0, region["y"] - pad)
        x2 = min(w, region["x"] + region["w"] + pad)
        y2 = min(h, region["y"] + region["h"] + pad)
        face_crop = img_rgb[y1:y2, x1:x2]

        pil_face = Image.fromarray(face_crop)

        # Save cropped face to disk alongside the original
        cropped_path = image_path.rsplit(".", 1)[0] + "_face_cropped.jpg"
        pil_face.save(cropped_path, "JPEG", quality=95)

        # Also return as raw bytes (used for imgbb upload)
        buf = io.BytesIO()
        pil_face.save(buf, "JPEG", quality=95)
        face_bytes = buf.getvalue()

        return {
            "embedding":     embedding,
            "embedding_len": len(embedding),
            "face_bytes":    face_bytes,
            "cropped_path":  cropped_path,
            "region":        region,
            "face_count":    len(results),
        }
