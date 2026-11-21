import subprocess
import time
import os

adb_serial = '192.168.8.11:43517'
out_dir = 'C:/Users/Administrator/Desktop/My Produk/App Android/Dicebot Android/doc/screenshots'
os.makedirs(out_dir, exist_ok=True)

def adb_cmd(cmd):
    full = f'adb -s {adb_serial} {cmd}'
    res = subprocess.run(full, shell=True, capture_output=True, text=True)
    return res.stdout

def tap(x, y, wait=1.0):
    adb_cmd(f'shell input tap {x} {y}')
    time.sleep(wait)

def dismiss():
    adb_cmd('shell input keyevent KEYCODE_BACK')
    time.sleep(0.8)

def capture(name):
    adb_cmd(f'shell screencap -p /sdcard/{name}.png')
    adb_cmd(f'pull /sdcard/{name}.png "{out_dir}/{name}.png"')
    print(f'Captured {name}.png')

subprocess.run(f'adb connect {adb_serial}', shell=True)
time.sleep(1)

# Wake up screen
adb_cmd('shell input keyevent KEYCODE_WAKEUP')
adb_cmd('shell input keyevent 82')
time.sleep(0.5)

# Bring app to front
adb_cmd('shell am start -n com.raptech.dicebot/.MainActivity')
time.sleep(1.5)

# Capture initial main screen
capture('dicebot_main_screen')

# Tab bar is around y = 620 on 720x1600 screen:
# Tab 0 (Chart): x = 90
# Tab 1 (History): x = 270
# Tab 2 (LUA): x = 450
# Tab 3 (Logs): x = 630

print('Testing Tab 1: History...')
tap(270, 620)
capture('dicebot_tab_history')

print('Testing Tab 2: LUA Script Editor...')
tap(450, 620)
capture('dicebot_tab_lua')

print('Testing Tab 3: Live Logs...')
tap(630, 620)
capture('dicebot_tab_logs')

# Switch back to Tab 0
tap(90, 620)

# Test Coin Selector Dialog: top coin chip around x = 360, y = 80
print('Testing Coin Selector Dialog...')
tap(360, 80)
capture('dicebot_dialog_coin')
dismiss()

# Test Risk Dialog: shield icon in control bar around x = 650, y = 1480
print('Testing Risk Config Dialog...')
tap(650, 1480)
capture('dicebot_dialog_risk')
dismiss()

print('All UI components and dialogs tested!')
