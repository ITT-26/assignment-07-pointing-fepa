import sys
import cv2
import time
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from collections import deque
import math
import threading
import pynput
import ctypes
from enum import IntEnum

VIDEO_ID = 0
NUM_HANDS = 1
MODEL_PATH = './hand_landmarker.task'
FACE_MODEL_PATH = './face_landmarker.task'

OPTIONS = vision.HandLandmarkerOptions(
    base_options=python.BaseOptions(model_asset_path=MODEL_PATH),
    num_hands=NUM_HANDS,
    running_mode=vision.RunningMode.VIDEO,
    min_hand_detection_confidence=0.5,
    min_hand_presence_confidence=0.5,
    min_tracking_confidence=0.5
)
OPTIONS_FACE = vision.FaceLandmarkerOptions(
    base_options=python.BaseOptions(model_asset_path=FACE_MODEL_PATH),
    running_mode=vision.RunningMode.VIDEO,
    output_face_blendshapes=True,
    output_facial_transformation_matrixes=True,
    num_faces=1
)

#asked local 26b gemma-4 model how to get resolution without installing extra package (tkinter was too unreliable)
ctypes.windll.shcore.SetProcessDpiAwareness(1)
SCREEN_WIDTH = ctypes.windll.user32.GetSystemMetrics(0)
SCREEN_HEIGHT = ctypes.windll.user32.GetSystemMetrics(1)

class ControlMode(IntEnum):
    MOUSE = 1
    PINCH = 2
    WINK = 3

class FingerTracker():
    def __init__(self, screenSize = (SCREEN_WIDTH,SCREEN_HEIGHT), mode = ControlMode.PINCH, showDebug = False):
        self.showDebugWindow = showDebug
        self.position = None
        self.isClicking = False
        self.screenSize = (SCREEN_WIDTH, SCREEN_HEIGHT)
        self.mode = mode
        self.initializeTracking()
        self.delay_queue = deque() 
        self.mouse = pynput.mouse.Controller()

    def initializeTracking(self):
        self.detector = vision.HandLandmarker.create_from_options(OPTIONS)
        self.detectorFace = vision.FaceLandmarker.create_from_options(OPTIONS_FACE)

        self.cap = cv2.VideoCapture(VIDEO_ID)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        self.camWidth = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.camHeight = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def startTracking(self):
        self.is_running = True
        self.thread = threading.Thread(target=self.tracking_loop, daemon=True)
        self.thread.start()
    
    def stopTracking(self):
        self.is_running = False
        self.cap.release()
        cv2.destroyAllWindows()

    def tracking_loop(self):
        lastFrameTime = time.time()
        while self.is_running:
            ret, frame = self.cap.read()
            if not ret or lastFrameTime > time.time() - 1/60:
                continue

            frame = cv2.flip(frame, 1)
            mp_frame = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
            timestamp_ms = int(time.time() * 1000)

            hands_detection_result = self.detector.detect_for_video(mp_frame, timestamp_ms)
            face_detection_result = self.detectorFace.detect_for_video(mp_frame, timestamp_ms)

            current_position = None
            cv_track_pos = None
            
            cvX, cvY = None, None #IndexFingertip
            cvXThumb, cvYThumb = None, None #ThumbTip
            cvMiddleX, cvMiddleY = None, None #Middle of the two

            if hands_detection_result.hand_landmarks:
                tip = hands_detection_result.hand_landmarks[0][8]       
                thumbtip = hands_detection_result.hand_landmarks[0][4]

                #Position relative to screenSize
                x = int(tip.x * self.screenSize[0])
                y = int(tip.y * self.screenSize[1])
                thumbX = int(thumbtip.x * self.screenSize[0])
                thumbY = int(thumbtip.y * self.screenSize[1])
                middleX = (thumbX + x) // 2
                middleY = (thumbY + y) // 2

                #Position relative to Webcam Frame
                cvX = int(tip.x * self.camWidth)
                cvY = int(tip.y * self.camHeight)
                cvXThumb = int(thumbtip.x * self.camWidth)
                cvYThumb = int(thumbtip.y * self.camHeight)
                cvMiddleX = (cvX + cvXThumb) // 2
                cvMiddleY = (cvY + cvYThumb) // 2

                if self.mode == ControlMode.WINK:
                    current_position = (x, y)
                    cv_track_pos = (cvX, cvY)

                    #Click by winking
                    if face_detection_result.face_blendshapes:
                        blendShapes = face_detection_result.face_blendshapes[0]
                        blinkLeft = next(bs.score for bs in blendShapes if bs.category_name == "eyeBlinkLeft")
                        blinkRight = next(bs.score for bs in blendShapes if bs.category_name == "eyeBlinkRight")

                        if (blinkLeft > 0.60 and blinkRight < 0.4) or (blinkRight > 0.60 and blinkLeft < 0.4):
                            if not self.isClicking:
                                self.isClicking = True
                                self.mouse.click(pynput.mouse.Button.left, 1)
                        else:
                            self.isClicking = False

                #Click by pinching
                elif self.mode == ControlMode.PINCH:
                    current_position = (middleX, middleY)
                    cv_track_pos = (cvMiddleX, cvMiddleY)

                    distance = math.hypot(tip.x - thumbtip.x, tip.y - thumbtip.y)
                    if distance < 0.035:
                        if not self.isClicking:
                            self.mouse.click(pynput.mouse.Button.left, 1)
                            self.isClicking = True
                        else:
                            self.isClicking = False
                    else:
                        self.isClicking = False

            #Move the mouse
            if current_position:
                self.mouse.position = current_position
                self.position = current_position

            #Just for Debugging/Running standalone
            if self.showDebugWindow and hands_detection_result.hand_landmarks:
                cv2.line(frame, (cvX, cvY), (cvXThumb, cvYThumb), (255, 255, 255), 2)
                
                cv2.circle(frame, (cvX, cvY), 5, (0, 0, 255), -1)
                cv2.circle(frame, (cvXThumb, cvYThumb), 5, (255, 0, 0), -1)

                if cv_track_pos:
                    cv2.circle(frame, cv_track_pos, 10, (0, 255, 0), -1)

                cv2.imshow("Hand Tracking Preview", frame)
            lastFrameTime = time.time()

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        self.cap.release()
        cv2.destroyAllWindows()


MODE = ControlMode.WINK
if __name__ == "__main__":
    v_id = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    #n_hands = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    
    tracker = FingerTracker(mode=MODE, showDebug=True)
    tracker.startTracking()
    
    try:
        while True:
            time.sleep(0.1)
            if not tracker.is_running:
                break
    except KeyboardInterrupt:
        tracker.stopTracking()