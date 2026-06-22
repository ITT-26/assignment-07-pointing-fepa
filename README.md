[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/KfEU5Azw)


## Requirements
- Python **3.9 - 3.12** (tensorflow/keras don't work on higher versions)

## Initializing and starting Virtual Enviroment

### For Windows
Open The Root-Directory (Assignment-05-...) in a Terminal and create + activate the virtual enviroment with (**make sure you use a supported version**):
````
py -3.12 -m venv venv
venv\Scripts\activate
````
(venv) should now be displayed before your new CommandLine in the Terminal

Next install the requirements:
````
pip install -r requirements.txt
````

### For Mac
The Steps are the same, but the concrete commands different:
````
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
````
<hr style="border: 2px solid #444; margin: 60px 0;">

# Table of Contents

| Task | Name |
|-|-|
| 01 | [Pose-Based Pointing Technique](#01-pose-based-pointing-technique) |
| 02 | [Fitts-Law](#02-fitts-law) |
| 03 | [Steering-Law](#03-steering-law) |
| 05 | [Analysis of Results](#05-analysis-of-results) |

# 01-Pose-Based Pointing Technique
1. You can start the file on it's own to see your camera feed with the pointers marked
    ````
    py -m pointing_input.py --pId 1
    ````
2. There are 2 different inputtypes
    - Your pointer is the middle-point of IndexFinger and Thumb  
      You click by pinching them together for 150ms
    - Your pointer is the IndexFingerTip  
      You click by winking with one eye
3. You can switch InputMode by pressing **_N_**
4. For the Following Tests the Class gets loaded automatically, no need to start it twice

# 02-Fitts-Law
1. Start with
    ````
    py -m fitts_law.py
    ````
    To go through a normal testround with 9 Combinations of distance and Size (pId is random between 0-9999)  
    **So make sure to not restart/set the correct pId if you do**

    All possible arguments are:
    ````
    py -m fitts_law.py --pId 1 --distance 500 --circleSize 40 --numTrials 3 --numCircles 10 --delay 150
    ````
     Argument | Type | Default | Description |
    | :--- | :--- | :--- | :--- |
    | `--pId` | `int` | random(0-9999) | ID for the player |
    | `--distance` | `int` | *Config* | Target distance |
    | `--circleSize` | `int` | *Config* | Size of the target circle |
    | `--numTrials` | `int` | `3` | Number of Iterations per condition |
    | `--numCircles` | `int` | `10` | number of circles |
    | `--delay` | `int` | `0` | Input-Delay (in ms) |

    > **Note:**   
    When not setting the `--distance` **and** `--circleSize` parameters,  
    the experiment follows the predefined sequence from the configuration.
    
2. Shortcuts
    | Shortcut | Function |
    | --- | --- |
    | **_S_** | Start a Round |
    | **_N_** | Skips current Distance/Width |
    | **_Q_** | Closes the Window |
3. After all Iterations of a combination are done a csv is saved automatically

# 03-Steering-Law
1. Start with
    ````
    py -m steering_law.py
    ````
    To go through a normal testround with 9 Combinations of distance and height

    All possible arguments are:
    ````
    py -m fitts_law.py --pId 1 --distance 500 --circleSize 40 --numTrials 3 --numCircles 10 --delay 150
    ````
     Argument | Type | Default | Description |
    | :--- | :--- | :--- | :--- |
    | `--pId` | `int` | random(0-9999) | Unique identifier for the player |
    | `--tunnelWidth` | `int` | *Config* | Tunnel Width |
    | `--tunnelHeight` | `int` | *Config* | Tunnel Height |
    | `--numTrials` | `int` | `3` | Number of Iterations per condition |
    | `--delay` | `int` | `0` | Input-Delay (in ms) |

    > **Note:**   
    When not setting the `--tunnelWidth` **and** `--tunnelHeight` parameters,  
    the experiment follows the predefined sequence from the configuration.
    
2. Shortcuts
    | Shortcut | Function |
    | --- | --- |
    | **_S_** | Start a Round |
    | **_N_** | Skips current Distance/Width |
    | **_Q_** | Closes the Window |
3. To start a iteration press **_S_** (it will warn you if your pointer is too far right)  
   Then enter the tunnel (tracking will start automatically) => Tracking will stop once the pointer crosses the "finishline"
4. After all Iterations of a combination are done a csv is saved automatically

# 05-Analysis of Results