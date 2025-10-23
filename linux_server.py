import socket
import threading
import subprocess
import os
import sys

# Try to import uinput, but don't fail immediately if it's not needed.
try:
    import uinput
except ImportError:
    uinput = None

# --- Configuration ---
TCP_HOST = '0.0.0.0'
TCP_PORT = 65432
UDP_PORT = 65433

# --- Abstraction Layer for Input Control ---

class InputController:
    """Base class defining the interface for an input controller."""
    def move_mouse(self, dx, dy):
        raise NotImplementedError
    def click(self, button):
        raise NotImplementedError
    def press_key(self, key):
        raise NotImplementedError
    def press_media_key(self, key_name):
        raise NotImplementedError
    def scroll(self, amount):
        raise NotImplementedError

class X11Controller(InputController):
    """Controls input using the xdotool command for X11."""
    def __init__(self):
        print("✅ Initialized X11 Input Controller.")

    def move_mouse(self, dx, dy):
        subprocess.run(["xdotool", "mousemove_relative", "--", str(dx), str(dy)])

    def click(self, button):
        button_map = {'left': '1', 'right': '3', 'middle': '2'}
        subprocess.run(["xdotool", "click", button_map.get(button, '1')])

    def press_key(self, key):
        subprocess.run(["xdotool", "key", key])
    
    def press_media_key(self, key_name):
        key_map = {
            'volumeup': 'XF86AudioRaiseVolume',
            'volumedown': 'XF86AudioLowerVolume',
            'volumemute': 'XF86AudioMute'
        }
        if key_name in key_map:
            subprocess.run(["xdotool", "key", key_map[key_name]])

    def scroll(self, amount):
        button = '4' if amount > 0 else '5' # 4=up, 5=down
        for _ in range(abs(amount)):
            subprocess.run(["xdotool", "click", button])

class WaylandController(InputController):
    """Controls input by creating a virtual uinput device for Wayland."""
    def __init__(self):
        if not uinput:
            print("❌ 'python-uinput' library is not installed. Please run 'pip install python-uinput'")
            sys.exit(1)
        
        events = (
            uinput.REL_X, uinput.REL_Y, uinput.REL_WHEEL,
            uinput.BTN_LEFT, uinput.BTN_RIGHT, uinput.BTN_MIDDLE, 
            uinput.KEY_A, uinput.KEY_B, uinput.KEY_C, uinput.KEY_SPACE, uinput.KEY_ENTER,
            uinput.KEY_VOLUMEUP, uinput.KEY_VOLUMEDOWN, uinput.KEY_MUTE,
        )
        
        try:
            self.device = uinput.Device(events, name="virtual-ios-remote")
        except PermissionError:
            print("❌ Permission Denied. Wayland controller must be run with sudo.")
            sys.exit(1)
            
        print("✅ Initialized Wayland Input Controller (virtual device created).")
        self.key_map = self._create_key_map()

    def _create_key_map(self):
        return {
            'a': uinput.KEY_A, 'b': uinput.KEY_B, 'c': uinput.KEY_C, # etc.
            'space': uinput.KEY_SPACE, 'enter': uinput.KEY_ENTER,
            'volumeup': uinput.KEY_VOLUMEUP,
            'volumedown': uinput.KEY_VOLUMEDOWN,
            'volumemute': uinput.KEY_MUTE
        }

    def move_mouse(self, dx, dy):
        self.device.emit(uinput.REL_X, dx, syn=False)
        self.device.emit(uinput.REL_Y, dy)

    def click(self, button):
        button_map = {
            'left': uinput.BTN_LEFT,
            'right': uinput.BTN_RIGHT,
            'middle': uinput.BTN_MIDDLE
        }
        self.device.emit_click(button_map.get(button, uinput.BTN_LEFT))
    
    def press_key(self, key):
        if key.lower() in self.key_map:
            self.device.emit_click(self.key_map[key.lower()])

    def press_media_key(self, key_name):
        self.press_key(key_name)

    def scroll(self, amount):
        direction_val = -1 if amount > 0 else 1
        for _ in range(abs(amount)):
            self.device.emit(uinput.REL_WHEEL, direction_val)


# --- Network Handling (These functions are now generic) ---

def handle_tcp_client(conn, addr, controller):
    print(f"TCP connection from {addr}")
    try:
        while True:
            data = conn.recv(1024)
            if not data: break
            command = data.decode('utf-8').strip().split(',')
            action = command[0]

            if action == 'mclick': controller.click(command[1])
            elif action == 'kpress': controller.press_key(command[1])
            elif action == 'vol': controller.press_media_key(command[1].replace('volume',''))
            # Power commands are OS-level, not display-server-level
            elif action == 'power': handle_power_command(command[1])

    except ConnectionResetError:
        print(f"Client {addr} disconnected.")
    finally:
        conn.close()

def handle_power_command(sub_command):
    cmd = []
    if sub_command == 'shutdown': cmd = ["systemctl", "poweroff"]
    elif sub_command == 'restart': cmd = ["systemctl", "reboot"]
    elif sub_command == 'sleep': cmd = ["systemctl", "suspend"]
    elif sub_command == 'lock': cmd = ["loginctl", "lock-session"]
    if cmd: subprocess.run(cmd)

def start_udp_server(controller):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind((TCP_HOST, UDP_PORT))
        print(f"🚀 UDP Server listening on port {UDP_PORT}...")
        while True:
            data, _ = s.recvfrom(1024)
            try:
                command = data.decode('utf-8').strip().split(',')
                action = command[0]
                if action == 'mmove': controller.move_mouse(int(command[1]), int(command[2]))
                elif action == 'scroll': controller.scroll(int(command[1]))
            except Exception as e:
                print(f"UDP Error: {e}")

def start_tcp_server(controller):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((TCP_HOST, TCP_PORT))
        s.listen()
        print(f"🚀 TCP Server listening on port {TCP_PORT}...")
        while True:
            conn, addr = s.accept()
            thread = threading.Thread(target=handle_tcp_client, args=(conn, addr, controller))
            thread.start()

# --- Main Execution ---
if __name__ == "__main__":
    print("--- Starting Linux Remote Control Server ---")
    
    # Detect the session type to choose the correct controller
    session_type = os.environ.get('XDG_SESSION_TYPE')
    print(f"Detected session type: {session_type}")
    
    controller = None
    if session_type == 'wayland':
        controller = WaylandController()
    elif session_type == 'x11':
        controller = X11Controller()
    else:
        print(f"⚠️ Unknown or unsupported session type: '{session_type}'. Defaulting to X11.")
        controller = X11Controller()

    # Start network threads
    tcp_thread = threading.Thread(target=start_tcp_server, args=(controller,))
    udp_thread = threading.Thread(target=start_udp_server, args=(controller,))
    
    tcp_thread.start()
    udp_thread.start()
    
    tcp_thread.join()
    udp_thread.join()
