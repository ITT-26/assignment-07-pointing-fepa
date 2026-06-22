import sys
import cv2
import time
import mediapipe as mp
import numpy as np
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

#Bounds for cam handtracking => So the inner 3/4 of the frame gets tanslated to 100% of the screen since handdetection doesnt work reliably at border of frame (this way whole hand is always in frame)
LOWER_BOUND = 0.25
UPPER_BOUND = 0.75

#conficende values could use some more finetuning
OPTIONS = vision.HandLandmarkerOptions(
    base_options=python.BaseOptions(model_asset_path=MODEL_PATH),
    num_hands=NUM_HANDS,
    running_mode=vision.RunningMode.VIDEO,
    min_hand_detection_confidence=0.4,
    min_hand_presence_confidence=0.5,
    min_tracking_confidence=0.4
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
    MOUSE = 0
    PINCH = 1
    WINK = 2
    TRACK_PAD = 3
    MOUSE_DELAY = 4

class FingerTracker():
    def __init__(self, mode = ControlMode.PINCH, showDebug = False, standalone = False):
        self.standAlone = standalone
        self.showDebugWindow = showDebug
        self.position = None
        self.isClicking = False
        self.screenSize = (SCREEN_WIDTH, SCREEN_HEIGHT)
        self.isRunning = False
        self.detector = vision.HandLandmarker.create_from_options(OPTIONS)
        self.detectorFace = vision.FaceLandmarker.create_from_options(OPTIONS_FACE)
        self.mouse = pynput.mouse.Controller()
        self.changeMode(mode) #starts Tracking if its a cammode

    def initializeCam(self):
        self.cap = cv2.VideoCapture(VIDEO_ID)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        self.camWidth = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.camHeight = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def changeMode(self, controlMode:ControlMode):
        self.mode = controlMode
        isCamMode = (controlMode == ControlMode.PINCH or controlMode == ControlMode.WINK)
        if not self.isRunning and isCamMode:
            self.startTracking()
        elif self.isRunning and not isCamMode:
            self.stopTracking()

    def startTracking(self):
        self.isRunning = True
        self.initializeCam()
        self.thread = threading.Thread(target=self.tracking_loop, daemon=True)
        self.thread.start()
    
    def stopTracking(self):
        self.isRunning = False
        self.cap.release()
        cv2.destroyAllWindows()

    def tracking_loop(self):
        lastFrameTime = time.time() #To improve performance
        clickTime = time.time()
        timestamp_ms = int(time.time() * 1000)
        while self.isRunning:
            ret, frame = self.cap.read()
            if not ret or lastFrameTime > time.time() - 1/60:
                continue

            frame = cv2.flip(frame, 1)
            mp_frame = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
            timestamp_ms += 33 #monotonically increase....

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

                #Position relative to 3/4 of screenSize
                relX = np.interp(tip.x, [LOWER_BOUND, UPPER_BOUND], [0, 1])
                relY = np.interp(tip.y, [LOWER_BOUND, UPPER_BOUND], [0, 1])
                relThumbX = np.interp(thumbtip.x, [LOWER_BOUND, UPPER_BOUND], [0, 1])
                relThumbY = np.interp(thumbtip.y, [LOWER_BOUND, UPPER_BOUND], [0, 1])
                x = int(relX * self.screenSize[0])
                y = int(relY * self.screenSize[1])
                
                thumbX = int(relThumbX * self.screenSize[0])
                thumbY = int(relThumbY * self.screenSize[1])
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
                            if clickTime is None:
                                clickTime = time.time()
                            elif time.time() - clickTime >= 0.15: #Also to reduce accidents, one blink of an eye is approximatly 100-150ms
                                if not self.isClicking:
                                    self.isClicking = True
                                    self.mouse.click(pynput.mouse.Button.left, 1)
                        else:
                            clickTime = None
                            self.isClicking = False

                #Click by pinching
                elif self.mode == ControlMode.PINCH:
                    current_position = (middleX, middleY)
                    cv_track_pos = (cvMiddleX, cvMiddleY)

                    distance = math.hypot(tip.x - thumbtip.x, tip.y - thumbtip.y)
                    if distance < 0.035:
                        if clickTime is None:
                            clickTime = time.time()
                        elif time.time() - clickTime >= 0.15: #150ms timeout since tracking can occasionally jump randomly, and dont want a jumping fingertip to accidentally trigger a missclick (downside is a guaranteed 150ms slower time)
                            if not self.isClicking:
                                self.mouse.click(pynput.mouse.Button.left, 1)
                                self.isClicking = True
                       
                    else:
                        self.isClicking = False
                        clickTime = None
            
            #Move the mouse
            if current_position:
                self.mouse.position = current_position
                self.position = current_position

            #Just for Debugging/Running standalone
            if self.showDebugWindow:
                if hands_detection_result.hand_landmarks:
                    cv2.line(frame, (cvX, cvY), (cvXThumb, cvYThumb), (255, 255, 255), 2)
                    
                    cv2.circle(frame, (cvX, cvY), 5, (0, 0, 255), -1)
                    cv2.circle(frame, (cvXThumb, cvYThumb), 5, (255, 0, 0), -1)

                    if cv_track_pos:
                        cv2.circle(frame, cv_track_pos, 10, (0, 255, 0), -1)

                cv2.imshow("Hand Tracking Preview", frame)
            
            lastFrameTime = time.time()

            key = cv2.waitKey(1) & 0xFF
            if  key == ord('q'):
                break

            if key == ord('n') and self.standAlone:
                newMode = ControlMode.WINK if self.mode == ControlMode.PINCH else ControlMode.PINCH
                self.changeMode(newMode)

        self.cap.release()
        cv2.destroyAllWindows()


MODE = ControlMode.PINCH #Just for Standalone stuff
if __name__ == "__main__":
    v_id = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    
    tracker = FingerTracker(mode=MODE, showDebug=True, standalone=True)
    tracker.startTracking()
    
    try:
        while True:
            time.sleep(0.1)
            if not tracker.isRunning:
                break
    except KeyboardInterrupt:
        tracker.stopTracking()