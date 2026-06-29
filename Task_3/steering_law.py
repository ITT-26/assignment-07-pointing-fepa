import sys
import os

import json
import pyglet
import argparse
import time
from dataclasses import dataclass
from collections import deque
from random import randint, shuffle

curDir = os.path.dirname(os.path.abspath(__file__))
parentFolder = os.path.dirname(curDir)
if parentFolder not in sys.path:
    sys.path.append(parentFolder)
from Task_1.pointing_input import FingerTracker, ControlMode
#Notes:
# - Since I decided to implement the tracker as absolute Pointing device one could just "jump" through the tunnel
# - So there is a check at the start and end (+50p) to start the test (maybe checkpoints inbetween wouldn't be bad, like in racing games)

WINDOW_WIDTH = 1920
toSubtract = (pyglet.display.get_display().get_default_screen().height // 1080) * 30 #-30 since windowbar counts extra (i think its 30 for 1080p? on 4k monitors its 60?)
WINDOW_HEIGHT = 1080-toSubtract 
SAVE_PATH = f"{parentFolder}/Task_5/data/steering"

print(SAVE_PATH)

@dataclass
class SteeringConfig:
    playerId: int
    tunnelWidth: int
    tunnelHeight: int
    numberOfTrials: int
    delay: int

class CsvLogger:
    def __init__(self, config: SteeringConfig):
        self.config = config
        self.log_csv = []
        self.csvHeader = "input_mode;iteration;pid;delay;tunnel_w;tunnel_h;x;y;hit;timestamp\n"

    def addToCsv(self, currentIteration, x, y, hit, controlMode:ControlMode):
        csvString = (
            f"{controlMode.name};"
            f"{currentIteration};"
            f"{self.config.playerId};"
            f"{self.config.delay};"
            f"{self.config.tunnelWidth};"
            f"{self.config.tunnelHeight};"
            f"{x};"
            f"{y};"
            f"{hit};"
            f"{int(time.time() * 1000)}\n"
        )        
        self.log_csv.append(csvString)

    def saveCSV(self, controlMode:ControlMode):
        saveFolder = os.path.join(SAVE_PATH, controlMode.name)
        if not os.path.exists(saveFolder):
            os.makedirs(saveFolder)
        csvName = f"{saveFolder}/steering_{controlMode.name}_{self.config.tunnelWidth}_{self.config.tunnelHeight}_{self.config.playerId}.csv"
        with open(csvName, "w") as file:
            file.write(self.csvHeader + "".join(self.log_csv))

        self.log_csv.clear()

class SteeringExperiment:
    def __init__(self, config: SteeringConfig):
        self.curstomParameters = False
        self.customDelay = False

        if config.delay is not None and config.delay != 0:
            self.customDelay = True
        else:
            config.delay = 0

        self.config:SteeringConfig = config
        if config.tunnelWidth is None or config.tunnelHeight is None:
            self.loadRounds()
        else:
            self.curstomParameters = True

        self.window = pyglet.window.Window(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.window.set_location(0, toSubtract) # 60 since windowbar isn't included
        self.window.set_mouse_visible(False)

        self.infoLabel = pyglet.text.Label(
            text="Press S if you are ready",
            x=20,
            y=20,
            width= (WINDOW_WIDTH - self.config.tunnelWidth)//2,
            font_size=22,
            color=(255, 255, 255, 255),
            multiline=True,
            anchor_x="left",
            anchor_y="bottom"
        )

        self.modeLabel = pyglet.text.Label(
            text=f"Input: {ControlMode(0).name}\nPress N to skip ahead",
            x=20,
            y=WINDOW_HEIGHT-20,
            font_size=22,
            color=(255, 255, 255, 255),
            multiline=True,
            width=500,
            anchor_x="left",
            anchor_y="top"
        )

        self.controlMode = ControlMode(0)
        self.tracker = FingerTracker(mode=self.controlMode)
        self.csvLogger = CsvLogger(config)
        self.trackCircle = pyglet.shapes.Circle(WINDOW_WIDTH/2, WINDOW_HEIGHT/2, 10, color=(0,255,0))
        self.rectangleBatch = pyglet.graphics.Batch()
        self.createTunnel()

        self.roundRunning = False
        self.allowStart = False
        self.currentIteration = 1
        self.currentDistanceIndex = 0
        self.currentTunnelHeightIndex = 0
        self.startTime = None
       

        self.moveDeque = deque()
        self.initWindowFunctions()
        self.run()

    def loadRounds(self):
        with open(f"{curDir}/steering.config", "r", encoding="utf-8") as f:
            roundConfig = json.load(f)

        self.tunnelDistances = roundConfig["tunnelDistance"]
        self.tunnelHeights= roundConfig["tunnelHeight"]

        shuffle(self.tunnelDistances)
        shuffle(self.tunnelHeights)

        self.config.tunnelHeight = self.tunnelHeights[0]
        self.config.tunnelWidth = self.tunnelDistances[0]

    def initWindowFunctions(self):
        self.window.on_draw = self.on_draw
        self.window.on_key_press = self.on_key_press
        self.window.on_close = self.on_close
        self.window.on_mouse_motion = self.on_mouse_motion

    def run(self):
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
            _, position = self.moveDeque.popleft()
            self.trackCircle.position = position

        self.hitTestTunnel(self.trackCircle.x, self.trackCircle.y)
        if self.tracker.isClicking:
            self.trackCircle.color = (0,0,255)

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int):
        show_at = int(time.time()*1000) + self.config.delay
        self.moveDeque.append((show_at, (x, y)))
    
    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        show_at = int(time.time()*1000) + self.config.delay
        self.moveDeque.append((show_at, (x, y)))

    def movePoint(self,x,y):
        time.sleep(self.config.delay/1000)
        self.trackCircle.position = (x,y)

    def hitTestTunnel(self, x, y):
        self.rectangleTop.color = (255,255,255)
        self.rectAngleBottom.color = (255,255,255)
        rectTop = self.rectangleTop
        rectBottom = self.rectAngleBottom
        
        top_y = rectTop.y
        bottom_y = rectBottom.y + rectBottom.height

        hitX = x > rectTop.x and x < rectTop.x + rectTop.width
        hitTop = hitX and y+self.trackCircle.radius > top_y
        hitBottom = hitX and y-self.trackCircle.radius < bottom_y
        in_y_tunnel = bottom_y < y < top_y

        #+100 since due to nature of the fingertracking since it can "jump"
        if (int(x) > int(rectTop.x) and int(x) < int(rectTop.x+100)) and in_y_tunnel and not self.roundRunning and self.allowStart:
            print("EnterTunnel")
            self.infoLabel.text = "Trial running...\nCross the finish-line"
            self.roundRunning = True
            self.startTime = time.time()

        if (int(x) >= int(rectTop.x+rectTop.width) and int(x) <= int(rectTop.x+rectTop.width + 100)) and in_y_tunnel and self.roundRunning and self.allowStart:
            print("LeftTunnel")
            self.roundRunning = False
            took = time.time()- self.startTime
            self.newRound(tooktime=f"{took:.01f}ms")

        if self.roundRunning :
            hit = 0
            if hitTop:
                hit = 1
                self.rectangleTop.color = (255,100,100)
            if hitBottom:
                self.rectAngleBottom.color = (255,100,100)
                hit = 1
            self.csvLogger.addToCsv(self.currentIteration, x,y,hit, self.controlMode)                 

    def on_key_press(self, symbol, modifiers):
        key = pyglet.window.key
        if symbol == key.Q:
            pyglet.app.exit()
            os._exit(0)

        newX = (WINDOW_WIDTH - self.tunnelDistances[self.currentDistanceIndex])//2
        tooFarRight = self.trackCircle.x > newX
        print(newX, self.trackCircle.x)
        if symbol == key.S and not self.allowStart:
            if tooFarRight:
                self.infoLabel.text = "Please Move you mouse\nto the left side!"
            else:
                self.createTunnel()
                self.allowStart = True
                self.infoLabel.text = "To start\njust enter the tunnel"
        
        if symbol == key.N:
            if tooFarRight:
                self.infoLabel.text = "Please Move you mouse\nto the left side!"
            else:
                self.newRound(skipRound=True)
                self.createTunnel()
                self.allowStart = False
    
    def on_close(self):
        os._exit(0)

    def createTunnel(self):
        width, height = self.config.tunnelWidth, self.config.tunnelHeight

        middleY = WINDOW_HEIGHT //2
        middleX = WINDOW_WIDTH //2

        startX = middleX - width // 2
        endX = middleX + width // 2

        startYTop = middleY + height//2
        endYTop = WINDOW_HEIGHT
        
        startYBottom = 0
        endYBottom = middleY - height//2
        self.rectangleTop = pyglet.shapes.Rectangle(startX, startYTop, (endX - startX), (endYTop - startYTop), (255,255,255), batch=self.rectangleBatch)
        self.rectAngleBottom = pyglet.shapes.Rectangle(startX, startYBottom, (endX - startX), (endYBottom - startYBottom), (255,255,255), batch=self.rectangleBatch)
    
    def newRound(self, tooktime="-- ms", skipRound=False):
        self.roundRunning = False
        self.allowStart = False
        if skipRound:
            self.infoLabel.text = f"Click S once ready"
        else:
            self.infoLabel.text = f"Well Done!\n{self.currentIteration} of {self.config.numberOfTrials}\n{tooktime}\nPress S once ready"
        
        self.currentIteration += 1
        allIterationsDone = self.currentIteration >= self.config.numberOfTrials + 1
        if allIterationsDone or skipRound:
            #If skipped clear log else save
            if skipRound:
                self.csvLogger.log_csv.clear()
            else:
                self.infoLabel.text = f"Finished All Iterations {self.currentIteration-1} of {self.config.numberOfTrials}\n{tooktime}\nPress S once ready"
                self.csvLogger.saveCSV(self.controlMode)
            
            #reset current iteration
            self.currentIteration = 1

            #if customstart arguments there is only one trial/height so go straight to next device
            if self.curstomParameters:
                self.nextDevice()
            else:
                self.currentDistanceIndex = (self.currentDistanceIndex + 1) % len(self.tunnelDistances)
                if self.currentDistanceIndex == 0:
                    self.currentTunnelHeightIndex += 1

                if self.currentTunnelHeightIndex >= len(self.tunnelHeights):
                    self.infoLabel.text = f"FINISHED EVERYTHING"
                    self.nextDevice()

                self.config.tunnelWidth = self.tunnelDistances[self.currentDistanceIndex]
                self.config.tunnelHeight = self.tunnelHeights[self.currentTunnelHeightIndex]
                self.csvLogger.config = self.config  
        self.setInfoString()
    
    def nextDevice(self):
        #reset Variables
        self.roundRunning = False
        self.currentIteration = 1
        self.currentDistanceIndex = 0
        self.currentTunnelHeightIndex = 0
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
        infoString = f"Distance: {self.config.tunnelWidth} | Size: {self.config.tunnelHeight}"
        self.modeLabel.text = f"Input: {self.controlMode.name}\n{infoString}\nPress N to skip ahead"

    def on_draw(self):
        self.window.clear()
        self.rectangleBatch.draw()
        self.trackCircle.draw()
        self.infoLabel.draw()
        self.modeLabel.draw()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pId", type=int, default=randint(0,9999))
    parser.add_argument("--tunnelWidth", type=int, default=None)
    parser.add_argument("--tunnelHeight", type=int, default=None)
    parser.add_argument("--numTrials", type=int, default=3)
    parser.add_argument("--delay", type=int, default=None)
    args = parser.parse_args()

    print(args.pId)

    config = SteeringConfig(
        playerId = args.pId,
        tunnelWidth= args.tunnelWidth,
        tunnelHeight = args.tunnelHeight,
        numberOfTrials =  args.numTrials,
        delay = args.delay,
    )

    SteeringExperiment(config)

main()