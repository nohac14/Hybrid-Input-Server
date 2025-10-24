import socket
import threading
import subprocess
import os
import sys
import shutil
from zeroconf import ServiceInfo, Zeroconf

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
        # Check if xdotool command exists
        if not shutil.which("xdotool"):
            print("❌ 'xdotool' is not installed. Please install it to use the X11 controller.")
            print("   (e.g., 'sudo apt-get install xdotool' or 'sudo dnf install xdotool')")
            sys.exit(1)
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
        
        # First, build the map of all keys we will support
        self.key_map = self._create_key_map()
        
        # --- CORRECTED CODE STARTS HERE ---
        
        # Now, create the list of events based on that map
        # This ensures the device is registered to handle every key you've defined.
        key_events = self.key_map.values() 
        mouse_events = (
            uinput.REL_X, 
            uinput.REL_Y, 
            uinput.REL_WHEEL,
            uinput.BTN_LEFT, 
            uinput.BTN_RIGHT, 
            uinput.BTN_MIDDLE,
        )
        
        # Combine all mouse and keyboard events
        all_events = mouse_events + tuple(key_events)
        
        try:
            self.device = uinput.Device(all_events, name="virtual-ios-remote")
        except PermissionError:
            print("❌ Permission Denied. Wayland controller must be run with sudo.")
            sys.exit(1)
            
        print("✅ Initialized Wayland Input Controller (virtual device created).")

    def _create_key_map(self):
        key_map = {
            # --- Special & Editing Keys ---
            'enter': uinput.KEY_ENTER,
            'space': uinput.KEY_SPACE,
            'backspace': uinput.KEY_BACKSPACE,
            'tab': uinput.KEY_TAB,
            'esc': uinput.KEY_ESC,
            'delete': uinput.KEY_DELETE,
            'insert': uinput.KEY_INSERT,
            
            # --- Modifier Keys ---
            'leftshift': uinput.KEY_LEFTSHIFT,
            'rightshift': uinput.KEY_RIGHTSHIFT,
            'leftctrl': uinput.KEY_LEFTCTRL,
            'rightctrl': uinput.KEY_RIGHTCTRL,
            'leftalt': uinput.KEY_LEFTALT,
            'rightalt': uinput.KEY_RIGHTALT,
            'leftmeta': uinput.KEY_LEFTMETA,   # Windows/Super/Command key
            'rightmeta': uinput.KEY_RIGHTMETA, # Windows/Super/Command key
            
            # --- Arrow & Navigation Keys ---
            'up': uinput.KEY_UP,
            'down': uinput.KEY_DOWN,
            'left': uinput.KEY_LEFT,
            'right': uinput.KEY_RIGHT,
            'home': uinput.KEY_HOME,
            'end': uinput.KEY_END,
            'pageup': uinput.KEY_PAGEUP,
            'pagedown': uinput.KEY_PAGEDOWN,
            
            # --- Media Keys ---
            'volumeup': uinput.KEY_VOLUMEUP,
            'volumedown': uinput.KEY_VOLUMEDOWN,
            'volumemute': uinput.KEY_MUTE,
            
            # --- Punctuation & Symbols ---
            'semicolon': uinput.KEY_SEMICOLON,          # ;
            'apostrophe': uinput.KEY_APOSTROPHE,       # '
            'grave': uinput.KEY_GRAVE,                 # `
            'comma': uinput.KEY_COMMA,                 # ,
            'dot': uinput.KEY_DOT,                     # .
            'slash': uinput.KEY_SLASH,                 # /
            'backslash': uinput.KEY_BACKSLASH,         # \
            'minus': uinput.KEY_MINUS,                 # -
            'equal': uinput.KEY_EQUAL,                 # =
            'leftbrace': uinput.KEY_LEFTBRACE,         # [
            'rightbrace': uinput.KEY_RIGHTBRACE,       # ]
        }
        
        # Programmatically add letters (a-z)
        for i in range(26):
            char = chr(ord('a') + i)
            key_map[char] = getattr(uinput, f"KEY_{char.upper()}")
    
        # Programmatically add numbers (0-9)
        for i in range(10):
            key_map[str(i)] = getattr(uinput, f"KEY_{i}")

        # f-keys
        for i in range(1, 13):
            key_map[f'f{i}'] = getattr(uinput, f"KEY_F{i}")
    
        return key_map

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
            elif action == 'vol': controller.press_media_key('volume' + command[1])
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

def get_ip_address():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # doesn't even have to be reachable
            s.connect(('10.255.255.255', 1))
            IP = s.getsockname()[0]
        except Exception:
            IP = '127.0.0.1'
        finally:
            s.close()
        return IP
    
def register_service():
    local_ip = get_ip_address()
    # Get the computer's hostname
    hostname = socket.gethostname().split('.')[0]

    # Define the service we're broadcasting
    service_type = "_remotecontrol._tcp.local."
    service_name = f"{hostname}._remotecontrol._tcp.local."

    info = ServiceInfo(
        service_type,
        service_name,
        addresses=[socket.inet_aton(local_ip)],
        port=TCP_PORT,
        properties={'udp_port': str(UDP_PORT)}, # Send UDP port as metadata
        server=f"{hostname}.local.",
    )

    zeroconf = Zeroconf()
    print(f"📢 Broadcasting service '{hostname}' on {local_ip}:{TCP_PORT}...")
    zeroconf.register_service(info)
    # You would ideally have a zeroconf.close() on script exit
    # For this long-running server, we'll just let it run.


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
    
    # Start the Bonjour/Zeroconf service broadcasting in a separate thread
    zeroconf_thread = threading.Thread(target=register_service)
    zeroconf_thread.daemon = True # Allows main program to exit even if this thread is running
    zeroconf_thread.start()
    
    # Start network threads
    tcp_thread = threading.Thread(target=start_tcp_server, args=(controller,))
    udp_thread = threading.Thread(target=start_udp_server, args=(controller,))
    
    tcp_thread.start()
    udp_thread.start()
    
    tcp_thread.join()
    udp_thread.join()
