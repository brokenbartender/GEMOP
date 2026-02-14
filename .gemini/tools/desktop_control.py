import sys
import subprocess
import pyautogui

command = sys.argv[1]

if command == "open":
    subprocess.Popen(sys.argv[2:])
elif command == "click_image":
    location = pyautogui.locateOnScreen(sys.argv[2])
    if location:
        pyautogui.click(location)
elif command == "type":
    pyautogui.write(sys.argv[2], interval=0.05)
