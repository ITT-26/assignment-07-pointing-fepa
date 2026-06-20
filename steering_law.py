from pointing_input import FingerTracker, ControlMode
import json
import tkinter as tk
import os
import pyglet
import argparse
import time
from dataclasses import dataclass
from collections import deque
import ctypes

#Notes:
# - Since I decided to implement the tracker as absolute Pointing device one could just "jump" through the tunnel
# - So there is a check at the start and end (+50p) to start the test (maybe checkpoints inbetween wouldn't be bad, like in racing games)

root = tk.Tk()
root.withdraw()
WINDOW_WIDTH = 1920 #int(root.winfo_screenwidth())
WINDOW_HEIGHT = 1080#int(root.winfo_screenheight())

ctypes.windll.shcore.SetProcessDpiAwareness(1)
SCREEN_WIDTH = ctypes.windll.user32.GetSystemMetrics(0)
SCREEN_HEIGHT = ctypes.windll.user32.GetSystemMetrics(1)

MODE = ControlMode.WINK
SAVE_PATH = "data"
DELAY = 0

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
        self.csvHeader = "iteration;pid;delay;tunnel_w;tunnel_h;x;y;hit;timestamp\n"

    def addToCsv(self, currentIteration, x, y, hit):
        csvString = f"{currentIteration};{self.config.playerId};{self.config.delay};{self.config.tunnelWidth};{self.config.tunnelHeight};{x};{y};{hit};{int(time.time()*1000)}\n"
        self.log_csv.append(csvString)

    def saveCSV(self):
        print("SAving")
        csvName = f"{SAVE_PATH}/steering_{self.config.tunnelWidth}_{self.config.tunnelHeight}_{self.config.playerId}.csv"
        with open(csvName, "w") as file:
            file.write(self.csvHeader + "".join(self.log_csv))

        self.log_csv.clear()

class SteeringExperiment:
    def __init__(self, config: SteeringConfig):
        self.config = config
        self.window = pyglet.window.Window(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.window.set_mouse_visible(False)
        self.loadRounds()
        self.infoLabel = pyglet.text.Label(
            text="Press S if you are ready",
            x=20,
            y=WINDOW_HEIGHT-20,
            width= (WINDOW_WIDTH - self.config.tunnelWidth)//2,
            font_size=30,
            color=(255, 255, 255, 255),
            multiline=True,
            anchor_x="left",
            anchor_y="top"
        )

        self.tracker = FingerTracker((WINDOW_WIDTH,WINDOW_HEIGHT), mode=MODE)
        self.csvLogger = CsvLogger(config)
        self.trackCircle = pyglet.shapes.Circle(WINDOW_WIDTH/2, WINDOW_HEIGHT/2, 10, color=(0,255,0))
        self.rectangleBatch = pyglet.graphics.Batch()
        self.rectangleTop, self.rectAngleBottom = self.createTunnel()

        self.roundRunning = False
        self.allowStart = False
        self.currentIteration = 1
        self.currentTrial = 0
        self.subTrial = 0
        self.startTime = None

        self.moveDeque = deque()
        self.initWindowFunctions()
        self.run()

    def loadRounds(self):
        with open("steering.config", "r", encoding="utf-8") as f:
            roundConfig = json.load(f)

        self.tunnelDistances = roundConfig["tunnelDistance"]
        self.tunnelHeights= roundConfig["tunnelHeight"]

        self.config.tunnelHeight = self.tunnelHeights[0]
        self.config.tunnelWidth = self.tunnelDistances[0]

    def initWindowFunctions(self):
        self.window.on_draw = self.on_draw
        self.window.on_key_press = self.on_key_press
        self.window.on_close = self.on_close
        self.window.on_mouse_motion = self.on_mouse_motion

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

        if (int(x) > int(rectTop.x) and int(x) < int(rectTop.x+50)) and in_y_tunnel and not self.roundRunning and self.allowStart:
            print("EnterTunnel")
            self.roundRunning = True
            self.startTime = time.time()

        if (int(x) >= int(rectTop.x+rectTop.width) and int(x) <= int(rectTop.x+rectTop.width + 50)) and in_y_tunnel and self.roundRunning and self.allowStart:
            print("LeftTunnel")
            self.roundRunning = False
            took = time.time()- self.startTime
            self.newRound(took)

        if self.roundRunning :
            hit = 0
            if hitTop:
                hit = 1
                self.rectangleTop.color = (255,100,100)
            if hitBottom:
                self.rectAngleBottom.color = (255,100,100)
                hit = 1
            self.csvLogger.addToCsv(self.currentIteration, x,y,hit)                 

    def on_key_press(self, symbol, modifiers):
        key = pyglet.window.key
        if symbol == key.Q:
            pyglet.app.exit()
            os._exit(0)

        newX = (WINDOW_WIDTH - self.tunnelDistances[self.currentTrial])//2
        if symbol == key.S and not self.allowStart:
            if self.trackCircle.x > newX:
                self.infoLabel.text = "Please Move you mouse\nto the left side!"
            else:
                self.rectangleTop, self.rectAngleBottom = self.createTunnel()
                self.allowStart = True
                self.infoLabel.text = "To start\njust enter the tunnel"
    
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
        
        return pyglet.shapes.Rectangle(startX, startYTop, (endX - startX), (endYTop - startYTop), (255,255,255), batch=self.rectangleBatch), pyglet.shapes.Rectangle(startX, startYBottom, (endX - startX), (endYBottom - startYBottom), (255,255,255), batch=self.rectangleBatch)
        
    
    def newRound(self, took):
        self.allowStart = False
        self.roundRunning = False
        self.infoLabel.text = f"Took: {took:.2f}s\nWell Done!\nClick S once ready"

        self.currentIteration +=1
        if self.currentIteration >= self.config.numberOfTrials + 1:
            self.infoLabel.text = f"Finished All Iterations\n{self.currentIteration-1} of {self.config.numberOfTrials}"
            self.csvLogger.saveCSV()

            self.currentIteration = 1
            self.currentTrial = (self.currentTrial + 1) % len(self.tunnelDistances)
            if self.currentTrial == 0:
                self.subTrial += 1
            if self.subTrial >= len(self.tunnelHeights):
                self.infoLabel.text = f"FINISHED EVERYTHING"
                self.subTrial = 0
            else:
                self.config.tunnelWidth = self.tunnelDistances[self.currentTrial]
                self.config.tunnelHeight = self.tunnelHeights[self.subTrial]
                self.csvLogger.config = self.config
                
    def on_draw(self):
        self.window.clear()
        self.rectangleBatch.draw()
        self.trackCircle.draw()
        self.infoLabel.draw()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--userId", type=int, default=5)
    parser.add_argument("--tunnelWidth", type=int, default=800)
    parser.add_argument("--tunnelHeight", type=int, default=80)
    parser.add_argument("--numTrials", type=int, default=3)
    parser.add_argument("--delay", type=int, default=0)
    args = parser.parse_args()

    config = SteeringConfig(
        playerId = args.userId,
        tunnelWidth= args.tunnelWidth,
        tunnelHeight = args.tunnelHeight,
        numberOfTrials =  args.numTrials,
        delay = args.delay,
    )

    SteeringExperiment(config)

main()