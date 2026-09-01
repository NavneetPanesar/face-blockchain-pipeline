import io
import json
from deepface import DeepFace
from PIL import Image
import numpy as np
import cv2


class FaceDetector:
    def detect_and_encode(self, image_path: str) -> dict:
        """
        Detect the first face in image_path, return:
        - embedding (128-float list)
        - cropped face as JPEG bytes
        - cropped face saved path
        """
        # DeepFace.represent() detects + encodes in one call
        result = DeepFace.represent(
            img_path=image_path,
            model_name="Facenet",   # 128-dim embedding
            enforce_detection=True,
            detector_backend="opencv",
        )

        if not result:
            raise ValueError("No face detected in the image.")

        embedding = result[0]["embedding"]          # list[float], len=128
        region   = result[0]["facial_area"]         # {x, y, w, h}

        # Crop face from original image with padding
        img = cv2.imread(image_path)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w = img.shape[:2]
        pad = 30
        x1 = max(0, region["x"] - pad)
        y1 = max(0, region["y"] - pad)
        x2 = min(w, region["x"] + region["w"] + pad)
        y2 = min(h, region["y"] + region["h"] + pad)
        face_crop = img[y1:y2, x1:x2]

        # Save cropped face
        cropped_path = image_path.rsplit(".", 1)[0] + "_face.jpg"
        pil = Image.fromarray(face_crop)
        pil.save(cropped_path, "JPEG", quality=95)

        # Also return as bytes for upload
        buf = io.BytesIO()
        pil.save(buf, "JPEG", quality=95)
        face_bytes = buf.getvalue()

        return {
            "embedding":      embedding,
            "embedding_len":  len(embedding),
            "face_bytes":     face_bytes,
            "cropped_path":   cropped_path,
            "region":         region,
        }
