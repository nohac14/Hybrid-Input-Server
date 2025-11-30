#!/usr/bin/env python3
"""
WebSocket-enabled Remote Control Server
Supports both the iOS app (raw TCP/UDP) and web browser (WebSocket)
"""

import socket
import threading
import pyautogui
import subprocess
import sys
import asyncio
import websockets
from zeroconf import ServiceInfo, Zeroconf

# --- Configuration ---
TCP_HOST = '0.0.0.0'
TCP_PORT = 65432      # Port for iOS app TCP and WebSocket
UDP_PORT = 65433      # Port for iOS app UDP

# Disable PyAutoGUI fail-safe
pyautogui.FAILSAFE = False

# Store connected WebSocket clients
websocket_clients = set()

# --- Command Processing (shared by TCP and WebSocket) ---
def process_command(command_str, protocol="TCP"):
    """
    Process a command string from either TCP or WebSocket
    """
    print(f"{protocol} RX: {command_str.strip()}")
    command = command_str.strip().split(',')
    action = command[0]

    try:
        # --- Mouse Click Actions ---
        if action == 'mclick' and len(command) > 1:
            pyautogui.click(button=command[1].strip())

        # --- Mouse Movement (from WebSocket, replaces UDP) ---
        elif action == 'mmove' and len(command) == 3:
            dx, dy = int(command[1]), int(command[2])
            pyautogui.moveRel(dx, dy)

        # --- Scroll Action ---
        elif action == 'scroll' and len(command) == 2:
            scroll_amount = int(command[1])
            if sys.platform == "win32":
                scroll_amount *= 20
            pyautogui.scroll(scroll_amount)

        # --- Keyboard Press Actions ---
        elif action == 'kpress' and len(command) > 1:
            key_to_press = command[1].strip('\n\r')
            print(f"Executing key press: '{key_to_press}'")
            pyautogui.press(key_to_press)

        # --- Volume Control Actions ---
        elif action == 'vol' and len(command) > 1:
            direction = command[1]
            if direction == 'up':
                pyautogui.press('volumeup')
            elif direction == 'down':
                pyautogui.press('volumedown')
            elif direction == 'mute':
                pyautogui.press('volumemute')

        # --- System Power Actions ---
        elif action == 'power' and len(command) > 1:
            sub_command = command[1]
            cmd = []

            if sys.platform == "win32":
                if sub_command == 'shutdown':
                    cmd = ["shutdown", "/s", "/t", "0"]
                elif sub_command == 'restart':
                    cmd = ["shutdown", "/r", "/t", "0"]
                elif sub_command == 'sleep':
                    cmd = ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"]
                elif sub_command == 'lock':
                    cmd = ["rundll32.exe", "user32.dll,LockWorkStation"]

            elif sys.platform == "darwin":
                if sub_command == 'shutdown':
                    cmd = ["osascript", "-e", 'tell app "System Events" to shut down']
                elif sub_command == 'restart':
                    cmd = ["osascript", "-e", 'tell app "System Events" to restart']
                elif sub_command == 'sleep':
                    cmd = ["osascript", "-e", 'tell app "System Events" to sleep']
                elif sub_command == 'lock':
                    cmd = ["/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession", "-suspend"]
            
            if cmd:
                print(f"Executing: {' '.join(cmd)}")
                subprocess.run(cmd)

    except Exception as e:
        print(f"Error processing command '{command_str}': {e}")

# --- WebSocket Handler ---
async def handle_websocket(websocket):
    """
    Handle WebSocket connections from web browsers
    """
    client_addr = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
    print(f"✅ WebSocket connection established from {client_addr}")
    
    websocket_clients.add(websocket)
    
    try:
        async for message in websocket:
            process_command(message, protocol="WebSocket")
    except websockets.exceptions.ConnectionClosed:
        print(f"🔌 WebSocket connection closed from {client_addr}")
    finally:
        websocket_clients.discard(websocket)

async def start_websocket_server():
    """
    Start the WebSocket server on the same port as TCP
    """
    print(f"🚀 WebSocket Server listening on port {TCP_PORT}...")
    async with websockets.serve(handle_websocket, TCP_HOST, TCP_PORT):
        await asyncio.Future()  # Run forever

# --- TCP Handler (For iOS app) ---
def handle_tcp_client(conn, addr):
    """
    Handles incoming TCP connections from the iOS app
    """
    print(f"✅ TCP connection established from {addr}")
    
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break

            command_str = data.decode('utf-8')
            process_command(command_str, protocol="TCP")

    except ConnectionResetError:
        print(f"⚠️ Client {addr} disconnected unexpectedly.")
    finally:
        print(f"🔌 Closing TCP connection from {addr}")
        conn.close()

def start_tcp_server():
    """
    Note: TCP server disabled when WebSocket is running on the same port
    This is kept for reference if you want to run them on different ports
    """
    pass

# --- UDP Server (For iOS app high-frequency commands) ---
def start_udp_server():
    """
    Starts the UDP server for iOS app mouse movement and scrolling
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind((TCP_HOST, UDP_PORT))
        print(f"🚀 UDP Server listening on port {UDP_PORT}...")
        while True:
            data, addr = s.recvfrom(1024)
            try:
                command_str = data.decode('utf-8').strip()
                process_command(command_str, protocol="UDP")
            except Exception as e:
                print(f"UDP Error: {e} | Raw data: {data}")

def get_ip_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP
    
def register_service():
    local_ip = get_ip_address()
    hostname = socket.gethostname().split('.')[0]

    service_type = "_remotecontrol._tcp.local."
    service_name = f"{hostname}._remotecontrol._tcp.local."

    info = ServiceInfo(
        service_type,
        service_name,
        addresses=[socket.inet_aton(local_ip)],
        port=TCP_PORT,
        properties={'udp_port': str(UDP_PORT)},
        server=f"{hostname}.local.",
    )

    zeroconf = Zeroconf()
    print(f"📢 Broadcasting service '{hostname}' on {local_ip}:{TCP_PORT}...")
    zeroconf.register_service(info)

# --- Main Execution ---
if __name__ == "__main__":
    print("--- Starting Remote Control Server (WebSocket + UDP) ---")
    print(f"OS Detected: {sys.platform}")
    print(f"IP Address: {get_ip_address()}")
    
    # Start Zeroconf broadcasting
    zeroconf_thread = threading.Thread(target=register_service)
    zeroconf_thread.daemon = True
    zeroconf_thread.start()

    # Start UDP server in a thread (for iOS app)
    udp_thread = threading.Thread(target=start_udp_server)
    udp_thread.daemon = True
    udp_thread.start()

    # Run WebSocket server (for web app) - this is the main event loop
    try:
        asyncio.run(start_websocket_server())
    except KeyboardInterrupt:
        print("\n👋 Server shutting down...")
