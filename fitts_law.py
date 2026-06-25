from pointing_input import FingerTracker, ControlMode
import json
import math
import os
import pyglet
import argparse
import time
from dataclasses import dataclass
from random import randint, shuffle
from collections import deque

#Notes:
# - Last distance of fitts experiment is intentionally very far at border, so the gestureinputs get tested at their limit

WINDOW_WIDTH = 1920 
toSubtract = (pyglet.display.get_display().get_default_screen().height // 1080) * 30 #-30 since windowbar counts extra (i think its 30 for 1080p? on 4k monitors its 60?)
WINDOW_HEIGHT = 1080-toSubtract 
SAVE_PATH = "data/fitts"

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
        self.csvHeader = "input_mode;iteration;pid;delay;num_targets;target_w;target_d;target_id;miss_clicks;timestamp\n"

    def addToCsv(self, currentIteration, fittsId, controlMode:ControlMode, missClicks):
        csvString = (
            f"{controlMode.name};"
            f"{currentIteration};"
            f"{self.config.playerId};"
            f"{self.config.delay};"
            f"{self.config.circleNumber};"
            f"{self.config.circleSize};"
            f"{self.config.circleDistance};"
            f"{fittsId};"
            f"{missClicks};"
            f"{int(time.time() * 1000)}\n"
        )        
        self.log_csv.append(csvString)

    def saveCSV(self, controlMode:ControlMode):
        saveFolder = os.path.join(SAVE_PATH, controlMode.name)
        if not os.path.exists(saveFolder):
            os.makedirs(saveFolder)
        csvName = f"{saveFolder}/fitts_{controlMode.name}_{self.config.circleNumber}_{self.config.circleSize}_{self.config.circleDistance}_{self.config.delay}_{self.config.playerId}.csv"
        
        with open(csvName, "w") as file:
            file.write(self.csvHeader + "".join(self.log_csv))
        self.log_csv.clear()


class FittsExpermiment:
    def __init__(self, config:FittsConfig):    
        self.curstomParameters = False
        self.customDelay = False

        if config.delay is not None and config.delay != 0:
            self.customDelay = True
        else:
            config.delay = 0

        self.config:FittsConfig = config
        if config.circleDistance is None or config.circleSize is None:
            self.loadRounds()
        else:
            self.curstomParameters = True
     
        self.window = pyglet.window.Window(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.window.set_location(0, toSubtract) # toSubtract since the menubar isn't included
        self.window.set_mouse_visible(False)        

        self.controlMode = ControlMode(0)
        self.tracker = FingerTracker(mode=self.controlMode)
        self.csvLogger = CsvLogger(config)
        self.trackCircle = pyglet.shapes.Circle(WINDOW_WIDTH/2, WINDOW_HEIGHT/2, 10, color=(0,255,0))
        self.circleBatch = pyglet.graphics.Batch()
        self.createCircles()
        
        
        self.roundRunning = False
        self.currentIteration = 1 #Starting with 1 sincce the example you gave us also starts with 1 and not 0
        self.currentDistanceIndex = 0 #currentdistance index of the config
        self.currentSizeIndex = 0 #currentSize index of the config
        self.fittsProgress = 0 #Progress of the circles per iteration
        self.missClicks = 0
        
        
        self.moveDeque = deque()
        self.clickDeque = deque()
        
        
        self.initLabels()
        self.initWindowFunctions()
        self.run()

    def initLabels(self):
        self.infoLabel = pyglet.text.Label(
            text="Press S if you are ready",
            x=20,
            y=20,
            font_size=30,
            color=(255, 255, 255, 255),
            width=500,
            multiline=True,
            anchor_x="left",
            anchor_y="bottom"
        )
        self.modeLabel = pyglet.text.Label(
            text=f"",
            x=20,
            y=WINDOW_HEIGHT-20,
            font_size=30,
            color=(255, 255, 255, 255),
            multiline=True,
            width=500,
            anchor_x="left",
            anchor_y="top"
        )
        self.setInfoString()

    def loadRounds(self):
        with open("fitts.config", "r", encoding="utf-8") as f:
            roundConfig = json.load(f)

        self.targetDistances = roundConfig["targetDistances"]
        self.targetSizes = roundConfig["targetSizes"]

        shuffle(self.targetDistances)
        shuffle(self.targetSizes)

        self.config.circleDistance = self.targetDistances[0]
        self.config.circleSize = self.targetSizes[0] 

    def makeFittsOrder(self):
        order = []
        numberOfCircles = self.config.circleNumber
        direction = randint(0,1) == 1
        
        for i in range(numberOfCircles // 2):
            order.append(i)
            order.append(i + numberOfCircles // 2)

        if direction:
            order.reverse()        
    
        return order

    def initWindowFunctions(self):
        self.window.on_draw = self.on_draw
        self.window.on_key_press = self.on_key_press
        self.window.on_close = self.on_close
        self.window.on_mouse_press = self.on_mouse_press
        self.window.on_mouse_motion = self.on_mouse_motion
        self.window.on_mouse_drag = self.on_mouse_drag

    def run(self):
        pyglet.clock.schedule_interval(self.update, 1/60)
        pyglet.app.run()

    def update(self, dt):
        self.trackCircle.color = (138,7,131)
        if self.controlMode == ControlMode.PINCH or self.controlMode == ControlMode.WINK:
            if self.tracker.isClicking:
                self.trackCircle.color = (0,0,255)
            cur_pos = self.tracker.position
            if cur_pos is  None: 
                self.trackCircle.color = (255,0,0)

        now = int(time.time()*1000)
        while self.moveDeque and now >= self.moveDeque[0][0]:
            _, current_position = self.moveDeque.popleft()
            self.trackCircle.position = current_position

        while self.clickDeque and now >= self.clickDeque[0][0]:
            _, (x,y) = self.clickDeque.popleft()
            if self.controlMode == ControlMode.PINCH or self.controlMode == ControlMode.WINK:
                if self.tracker.isClicking:
                    self.trackCircle.color = (0,0,255)
            self.circleHitTest(x,y)
        

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int):
        show_at = int(time.time()*1000) + self.config.delay
        self.moveDeque.append((show_at, (x, y)))

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        show_at = int(time.time()*1000) + self.config.delay
        self.moveDeque.append((show_at, (x, y)))

    def on_mouse_press(self, x, y, button, modifiers):
        if button == pyglet.window.mouse.LEFT and self.roundRunning:
            show_at = int(time.time()*1000) + self.config.delay
            self.clickDeque.append((show_at, (x, y)))

    def on_key_press(self, symbol, modifiers):
        key = pyglet.window.key
        if symbol == key.Q:
            pyglet.app.exit()
            os._exit(0)
        if symbol == key.S and not self.roundRunning:
            self.roundRunning = True
            self.infoLabel.text = "Click on the marked Circle to beginn"
            self.createCircles()
            self.nextCircle()
        if symbol == key.N:
            self.newRound(True)
    
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

        self.fittsCircles = circles
        self.circleOrder = self.makeFittsOrder()
    
    def nextCircle(self):
        for i, circle in enumerate(self.fittsCircles):
            if i == self.circleOrder[self.fittsProgress]:
                circle.color = (0,255,50)
        
    def circleHitTest(self, mouseX, mouseY):
        missClick = True
        for i , circle in enumerate(self.fittsCircles):
            dx = mouseX - circle.x
            dy = mouseY - circle.y

            if math.sqrt(dx * dx + dy * dy) <= circle.radius:
                if i == self.circleOrder[self.fittsProgress]:
                    missClick = False
                    self.infoLabel.text = "Keep Going"
                    circle.color = (255,255,255)
                    self.csvLogger.addToCsv(self.currentIteration, self.fittsProgress+1, self.controlMode, self.missClicks)
                    self.missClicks = 0
                    self.fittsProgress = (self.fittsProgress + 1) % self.config.circleNumber
                    
                    if self.fittsProgress == 0:
                        self.newRound()
                    else:
                        self.nextCircle()
        if missClick:
            self.missClicks += 1

    def newRound(self, skipRound=False):
        self.roundRunning = False
        
        if skipRound:
            self.infoLabel.text = f"Click S once ready"
            self.fittsProgress = 0
        else:
            self.infoLabel.text = f"Well Done!\n{self.currentIteration} of {self.config.numberOfTrials}\nClick S once ready"
        
        self.currentIteration += 1
        allIterationsDone = self.currentIteration >= self.config.numberOfTrials + 1
        if allIterationsDone or skipRound:
            #If skipped clear log else save
            if skipRound:
                self.csvLogger.log_csv.clear()
            else:
                self.infoLabel.text = f"Finished All Iterations {self.currentIteration-1} of {self.config.numberOfTrials}"
                self.csvLogger.saveCSV(self.controlMode)
            
            #reset current iteration
            self.currentIteration = 1

            #if customstart arguments there is only one trial/currentSizeIndex so go straight to next device
            if self.curstomParameters:
                self.nextDevice()
            else:
                self.currentDistanceIndex = (self.currentDistanceIndex + 1) % len(self.targetDistances)
                if self.currentDistanceIndex == 0:
                    self.currentSizeIndex += 1

                if self.currentSizeIndex >= len(self.targetSizes):
                    self.infoLabel.text = f"FINISHED EVERYTHING"
                    self.nextDevice()

                self.config.circleDistance = self.targetDistances[self.currentDistanceIndex]
                self.config.circleSize = self.targetSizes[self.currentSizeIndex]
                self.csvLogger.config = self.config  

        self.createCircles()
        self.setInfoString()
    
    def nextDevice(self):
        #reset Variables
        self.roundRunning = False
        self.currentIteration = 1
        self.currentDistanceIndex = 0
        self.currentSizeIndex = 0
        self.fittsProgress = 0
        
        #set new inputdevice
        self.controlMode = ControlMode((self.controlMode.value+1) % len(ControlMode))
        self.tracker.setMode(self.controlMode)

        #really hate this check, but since both custom and the ready made test-runs should be possible this is a (bad) solution
        if not self.customDelay:
            #could be more elegant but this way, whenever one wants to add inputdevice with delay it can just be added to the name
            if "delay" in self.controlMode.name.lower():
                self.config.delay = 150
            else:
                self.config.delay = 0

        #if its back at 0 all input-devices are through
        if self.controlMode.value == 0:
            print("Done every combination of every controlmode")

    def setInfoString(self):
        infoString = f"Distance: {self.config.circleDistance} | Size: {self.config.circleSize}"
        self.modeLabel.text = f"Input: {self.controlMode.name}\n{infoString}\nPress N to skip ahead"

    def on_draw(self):
        self.window.clear()
        self.circleBatch.draw()
        self.trackCircle.draw()
        self.infoLabel.draw()
        self.modeLabel.draw()

#Not really necessary, just a little more readable
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pId", type=int, default=randint(0,9999))
    parser.add_argument("--distance", type=int, default=None)
    parser.add_argument("--circleSize", type=int, default=None)
    parser.add_argument("--numTrials", type=int, default=3)
    parser.add_argument("--numCircles", type=int, default=10)
    parser.add_argument("--delay", type=int, default=None)
    args = parser.parse_args()

    config = FittsConfig(
        playerId = args.pId,
        circleNumber = args.numCircles,
        circleDistance = args.distance,
        circleSize = args.circleSize,
        numberOfTrials =  args.numTrials,
        delay = args.delay,
    )

    FittsExpermiment(config)


main()