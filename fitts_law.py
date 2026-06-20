from pointing_input import FingerTracker, ControlMode
import json
import math
import os
import pyglet
import argparse
import time
from dataclasses import dataclass
from random import randint
from collections import deque
import ctypes

WINDOW_WIDTH = 1920 #int(root.winfo_screenwidth())
WINDOW_HEIGHT = 1080 #int(root.winfo_screenheight())

#asked local 26b gemma-4 model how to get resolution without installing extra package (tkinter was too unreliable)
ctypes.windll.shcore.SetProcessDpiAwareness(1)
SCREEN_WIDTH = ctypes.windll.user32.GetSystemMetrics(0)
SCREEN_HEIGHT = ctypes.windll.user32.GetSystemMetrics(1)

MODE = ControlMode.WINK
SAVE_PATH = "data"
DELAY = 150

@dataclass
class FittsConfig:
    playerId: int
    circleNumber: int
    circleDistance: int
    circleSize: int
    numberOfTrials: int
    delay: int

#could make variable with import csv + lists
class CsvLogger:
    def __init__(self, config: FittsConfig):
        self.config = config
        self.log_csv = []
        self.csvHeader = "iteration;pid;delay;num_targets;target_w;target_d;target_id;timestamp\n"

    def addToCsv(self, currentIteration, fittsId):
        csvString = f"{currentIteration};{self.config.playerId};{self.config.delay};{self.config.circleNumber};{self.config.circleSize};{self.config.circleDistance};{fittsId};{int(time.time()*1000)}\n"
        self.log_csv.append(csvString)

    def saveCSV(self):
        csvName = f"{SAVE_PATH}/fitts_{self.config.circleNumber}_{self.config.circleSize}_{self.config.circleDistance}_{self.config.delay}_{self.config.playerId}.csv"
        
        with open(csvName, "w") as file:
            file.write(self.csvHeader + "".join(self.log_csv))
        self.log_csv.clear()


class FittsExpermiment:
    def __init__(self, config):    
        self.config:FittsConfig = config
        self.loadRounds()
        self.window = pyglet.window.Window(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.window.set_mouse_visible(False)
        self.infoLabel = pyglet.text.Label(
            text="Press S if you are ready",
            x=20,
            y=20,
            font_size=30,
            color=(255, 255, 255, 255),
            anchor_x="left",
            anchor_y="bottom"
        )

        self.tracker = FingerTracker((SCREEN_WIDTH,SCREEN_HEIGHT),mode=MODE)
        self.csvLogger = CsvLogger(config)
        self.trackCircle = pyglet.shapes.Circle(WINDOW_WIDTH/2, WINDOW_HEIGHT/2, 10, color=(0,255,0))
        self.circleBatch = pyglet.graphics.Batch()
        self.fittsCircles = self.createCircles()
        self.circleOrder = self.makeFittsOrder()

        self.roundRunning = False
        self.currentIteration = 1 #Starting with 1 sincce the example you gave us also starts with 1 and not 0
        self.currentTrial = 0
        self.subTrial = 0
        self.fittsProgress = 0
        
        self.moveDeque = deque()
        self.clickDeque = deque()
        
        self.initWindowFunctions()
        self.run()

    def loadRounds(self):
        with open("fitts.config", "r", encoding="utf-8") as f:
            roundConfig = json.load(f)

        self.targetDistances = roundConfig["targetDistances"]
        self.targetSizes = roundConfig["targetSizes"]

        self.config.circleDistance = self.targetDistances[0]
        self.config.circleSize = self.targetSizes[0] 

    def makeFittsOrder(self):
        order = []
        numberOfCircles = self.config.circleNumber
        for i in range(numberOfCircles // 2):
            order.append(i)
            order.append(i + numberOfCircles // 2)
        return order

    def initWindowFunctions(self):
        self.window.on_draw = self.on_draw
        self.window.on_key_press = self.on_key_press
        self.window.on_close = self.on_close
        self.window.on_mouse_press = self.on_mouse_press
        self.window.on_mouse_motion = self.on_mouse_motion
        self.window.on_mouse_drag = self.on_mouse_drag

    def run(self):
        self.tracker.startTracking()
        pyglet.clock.schedule_interval(self.update, 1/60)
        pyglet.app.run()

    def update(self, dt):
        cur_pos = self.tracker.position
        if cur_pos is not None: 
            self.trackCircle.color = (138,7,131)
        else:
            self.trackCircle.color = (255,0,0)

        now = int(time.time()*1000)
        while self.moveDeque and now >= self.moveDeque[0][0]:
            _, current_position = self.moveDeque.popleft()
            self.trackCircle.position = current_position

        while self.clickDeque and now >= self.clickDeque[0][0]:
            _, (x,y) = self.clickDeque.popleft()
            self.circleHitTest(x,y)
        if self.tracker.isClicking:
            self.trackCircle.color = (0,0,255)

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int):
        show_at = int(time.time()*1000) + self.config.delay
        self.moveDeque.append((show_at, (x, y)))

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        show_at = int(time.time()*1000) + self.config.delay
        self.moveDeque.append((show_at, (x, y)))

    def movePoint(self,x,y):
        if(self.config.delay > 0):
            time.sleep(self.config.delay/1000)
        self.trackCircle.position = (x,y)

    def on_mouse_press(self, x, y, button, modifiers):
        if button == pyglet.window.mouse.LEFT and self.roundRunning:
            show_at = int(time.time()*1000) + self.config.delay
            self.clickDeque.append((show_at, (x, y)))

    def mouse_press(self,x,y):
        if(self.config.delay > 0):
            time.sleep(self.config.delay/1000)
        self.circleHitTest(x,y)

    def on_key_press(self, symbol, modifiers):
        key = pyglet.window.key
        if symbol == key.Q:
            pyglet.app.exit()
            os._exit(0)
        if symbol == key.S and not self.roundRunning:
            self.roundRunning = True
            self.infoLabel.text = "Click on the marked Circle to beginn"
            self.fittsCircles = self.createCircles()
            self.nextCircle()
    
    def on_close(self):
        os._exit(0)

    def createCircles(self):
        centerX, centerY = self.window.width // 2, self.window.height // 2
        number = self.config.circleNumber    
        circleSize = self.config.circleSize
        radius = self.config.circleDistance

        circles = []
        randomTwist = randint(90,270)
        for i in range(number):
            angle = 2 * math.pi * i / number + randomTwist
            x = centerX + math.cos(angle) * radius
            y = centerY + math.sin(angle) * radius
            circles.append(
                pyglet.shapes.Circle(x, y, circleSize, color=(255, 255, 255), batch=self.circleBatch)
            )
        return circles
    
    def nextCircle(self):
        for i, circle in enumerate(self.fittsCircles):
            if i == self.circleOrder[self.fittsProgress]:
                circle.color = (0,255,50)
        
    def circleHitTest(self, mouseX, mouseY):
        for i , circle in enumerate(self.fittsCircles):
            dx = mouseX - circle.x
            dy = mouseY - circle.y

            if math.sqrt(dx * dx + dy * dy) <= circle.radius:
                if i == self.circleOrder[self.fittsProgress]:
                    self.infoLabel.text = "Keep Going"
                    circle.color = (255,255,255)
                    self.csvLogger.addToCsv(self.currentIteration, self.fittsProgress+1)

                    self.fittsProgress = (self.fittsProgress + 1) % self.config.circleNumber
                    
                    if self.fittsProgress == 0:
                        self.newRound()
                    else:
                        self.nextCircle()

    def newRound(self):
        self.roundRunning = False
        self.infoLabel.text = "Well Done! Click S once ready"
        self.currentIteration +=1

        if self.currentIteration >= self.config.numberOfTrials + 1:
            self.infoLabel.text = f"Finished All Iterations {self.currentIteration-1} of {self.config.numberOfTrials}"
            self.csvLogger.saveCSV()

            self.currentIteration = 1
            self.currentTrial = (self.currentTrial + 1) % len(self.targetDistances)
            if self.currentTrial == 0:
                self.subTrial += 1

            if self.subTrial >= len(self.targetSizes):
                self.infoLabel.text = f"FINISHED EVERYTHING"
            else:
                self.config.circleDistance = self.targetDistances[self.currentTrial]
                self.config.circleSize = self.targetSizes[self.subTrial]
                self.csvLogger.config = self.config
                
        print(self.config.circleDistance, "-" , self.targetSizes[self.subTrial])   
        
    def on_draw(self):
        self.window.clear()
        self.circleBatch.draw()
        self.trackCircle.draw()
        self.infoLabel.draw()

#Not really necessary, just a little more readable
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--userId", type=int, default=5)
    parser.add_argument("--distance", type=int, default=300)
    parser.add_argument("--circleSize", type=int, default=40)
    parser.add_argument("--numTrials", type=int, default=3)
    parser.add_argument("--numCircles", type=int, default=12)
    parser.add_argument("--delay", type=int, default=0)
    args = parser.parse_args()

    config = FittsConfig(
        playerId = args.userId,
        circleNumber = 10,
        circleDistance = args.distance,
        circleSize = args.circleSize,
        numberOfTrials =  args.numTrials,
        delay = args.delay,
    )

    FittsExpermiment(config)


main()