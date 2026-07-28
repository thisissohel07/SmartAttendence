import cv2
import numpy as np
import base64
import os
from io import BytesIO
from PIL import Image

def get_cascade_classifier():
    """Load OpenCV Haar Cascade for frontal face detection."""
    # Check local project path first
    local_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'haarcascade_frontalface_default.xml')
    if os.path.exists(local_path):
        return cv2.CascadeClassifier(local_path)
    
    # Fallback to cv2.data
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    if os.path.exists(cascade_path):
        return cv2.CascadeClassifier(cascade_path)
        
    raise FileNotFoundError(f"Haar cascade XML model file not found at {local_path} or {cascade_path}")


def base64_to_cv2_image(base64_str):
    """Convert base64 data URI string from webcam canvas into OpenCV BGR numpy array."""
    if ',' in base64_str:
        base64_str = base64_str.split(',')[1]
    image_data = base64.b64decode(base64_str)
    pil_image = Image.open(BytesIO(image_data)).convert('RGB')
    open_cv_image = np.array(pil_image)
    # Convert RGB to BGR
    return cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2BGR)


def check_anti_spoofing(gray_face):
    """
    Anti-spoofing check using Laplacian variance for sharpness/texture assessment.
    Screen photos and low-quality printed photos often yield abnormally high or low variance.
    Returns (is_real, reason)
    """
    laplacian_var = cv2.Laplacian(gray_face, cv2.CV_64F).var()
    # Extremely low variance (< 15) indicates blurred photo or screen glare
    if laplacian_var < 15.0:
        return False, "Photo/Screen attack suspected (Image too blurry/smooth)."
    return True, "Passed anti-spoofing check."


def detect_and_extract_face(bgr_image):
    """
    Detect face in image.
    Rules:
    - Exactly 1 face required.
    - If 0 faces: Return error "No face detected."
    - If > 1 face: Return error "Only one face allowed."
    Returns: (success, message, face_gray, bounding_box)
    """
    classifier = get_cascade_classifier()
    gray = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)
    
    # Enhance contrast with CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray_eq = clahe.apply(gray)

    faces = classifier.detectMultiScale(
        gray_eq,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(80, 80)
    )

    if len(faces) == 0:
        return False, "No face detected.", None, None
    elif len(faces) > 1:
        return False, "Only one face allowed.", None, None

    x, y, w, h = faces[0]
    face_roi = gray_eq[y:y+h, x:x+w]
    
    # Resize ROI to a standard 200x200 size for LBPH recognizer
    resized_face = cv2.resize(face_roi, (200, 200), interpolation=cv2.INTER_AREA)

    # Run Anti-spoofing check
    is_real, spoof_msg = check_anti_spoofing(resized_face)
    if not is_real:
        return False, spoof_msg, None, None

    return True, "Face detected successfully.", resized_face, (x, y, w, h)


def face_to_bytes(gray_face):
    """Convert 200x200 grayscale numpy image to PNG bytes for DB storage."""
    is_success, buffer = cv2.imencode('.png', gray_face)
    if is_success:
        return buffer.tobytes()
    raise ValueError("Failed to encode face image to bytes.")


def bytes_to_face(face_bytes):
    """Decode binary PNG/JPEG bytes back to 200x200 grayscale numpy array."""
    np_arr = np.frombuffer(face_bytes, np.uint8)
    gray_face = cv2.imdecode(np_arr, cv2.IMREAD_GRAYSCALE)
    if gray_face is None:
        raise ValueError("Failed to decode face bytes into image.")
    return cv2.resize(gray_face, (200, 200))


def check_duplicate_face(new_face_gray, existing_students, threshold=60.0):
    """
    Prevent duplicate face registration.
    Compares the newly captured face against all currently registered student faces.
    Returns: (is_duplicate, duplicate_student)
    """
    if not existing_students:
        return False, None

    labels = []
    faces = []
    student_map = {}

    for idx, student in enumerate(existing_students, start=1):
        if student.face_bytes:
            try:
                img = bytes_to_face(student.face_bytes)
                faces.append(img)
                labels.append(idx)
                student_map[idx] = student
            except Exception:
                continue

    if not faces:
        return False, None

    # Train LBPH Recognizer with existing faces
    recognizer = cv2.face.LBPHFaceRecognizer_create(radius=1, neighbors=8, grid_x=8, grid_y=8)
    recognizer.train(faces, np.array(labels))

    label, confidence = recognizer.predict(new_face_gray)
    
    # In LBPH, lower confidence number means closer match (0 is exact match)
    if confidence <= threshold:
        return True, student_map.get(label)

    return False, None


def verify_face(scanned_face_gray, student, threshold=70.0):
    """
    Verify scanned face against target student's stored face template.
    Returns: (is_match, confidence_score)
    """
    if not student or not student.face_bytes:
        return False, 0.0

    try:
        registered_face = bytes_to_face(student.face_bytes)
    except Exception as e:
        return False, 0.0

    recognizer = cv2.face.LBPHFaceRecognizer_create(radius=1, neighbors=8, grid_x=8, grid_y=8)
    recognizer.train([registered_face], np.array([1]))

    label, distance = recognizer.predict(scanned_face_gray)

    # Normalize LBPH distance to a percentage confidence score (100% = exact, 0% = far)
    # LBPH distance usually ranges from 0 to 120+
    confidence_score = max(0.0, round(100.0 - distance, 2))

    if distance <= threshold:
        return True, confidence_score
    else:
        return False, confidence_score
