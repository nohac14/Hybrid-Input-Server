import socket
import threading
import pyautogui
import subprocess
import sys

# --- Configuration ---
TCP_HOST = '0.0.0.0'  # Listen on all available network interfaces
TCP_PORT = 65432      # Port for reliable commands (TCP)
UDP_PORT = 65433      # Port for high-speed commands (UDP)

# Disable the PyAutoGUI fail-safe feature.
# This prevents the script from stopping if the mouse moves to a corner.
pyautogui.FAILSAFE = False

# --- TCP Handler (For reliable commands) ---
def handle_tcp_client(conn, addr):
    """
    Handles incoming TCP connections for commands like clicks, keys, volume, and power.
    """
    print(f"✅ TCP connection established from {addr}")
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break  # Connection closed by the client

            command_str = data.decode('utf-8').strip()
            print(f"TCP RX: {command_str}")
            command = command_str.split(',')
            action = command[0]

            # --- Mouse Click Actions ---
            if action == 'mclick' and len(command) > 1:
                pyautogui.click(button=command[1])

            # --- Keyboard Press Actions ---
            elif action == 'kpress' and len(command) > 1:
                pyautogui.press(command[1])

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

                if sys.platform == "win32":  # For Windows
                    if sub_command == 'shutdown':
                        cmd = ["shutdown", "/s", "/t", "0"]
                    elif sub_command == 'restart':
                        cmd = ["shutdown", "/r", "/t", "0"]
                    elif sub_command == 'sleep':
                        cmd = ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"]
                    elif sub_command == 'lock':
                        cmd = ["rundll32.exe", "user32.dll,LockWorkStation"]

                elif sys.platform == "darwin":  # For macOS
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
                else:
                    print(f"⚠️ Unknown power command for {sys.platform}: {sub_command}")

    except ConnectionResetError:
        print(f"⚠️ Client {addr} disconnected unexpectedly.")
    finally:
        print(f"🔌 Closing TCP connection from {addr}")
        conn.close()

def start_tcp_server():
    """
    Starts the TCP server to listen for incoming connections.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((TCP_HOST, TCP_PORT))
        s.listen()
        print(f"🚀 TCP Server listening on port {TCP_PORT}...")
        while True:
            conn, addr = s.accept()
            # Start a new thread for each client to handle multiple connections
            thread = threading.Thread(target=handle_tcp_client, args=(conn, addr))
            thread.start()

# --- UDP Server (For high-frequency, non-critical commands) ---
def start_udp_server():
    """
    Starts the UDP server for mouse movement and scrolling.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind((TCP_HOST, UDP_PORT))
        print(f"🚀 UDP Server listening on port {UDP_PORT}...")
        while True:
            data, addr = s.recvfrom(1024)
            try:
                command_str = data.decode('utf-8').strip()
                command = command_str.split(',')
                action = command[0]

                # --- Mouse Movement Action ---
                if action == 'mmove' and len(command) == 3:
                    dx, dy = int(command[1]), int(command[2])
                    pyautogui.moveRel(dx, dy)

                # --- Scroll Action ---
                elif action == 'scroll' and len(command) == 2:
                    scroll_amount = int(command[1])
                    pyautogui.scroll(scroll_amount)

            except Exception as e:
                print(f"UDP Error: {e} | Raw data: {data}")

# --- Main Execution Block ---
if __name__ == "__main__":
    print("--- Starting iOS Remote Control Server ---")
    print(f"OS Detected: {sys.platform}")

    # Create and start the TCP and UDP server threads
    tcp_thread = threading.Thread(target=start_tcp_server)
    udp_thread = threading.Thread(target=start_udp_server)

    tcp_thread.start()
    udp_thread.start()

    # Wait for the threads to complete (they won't, but this keeps the main script alive)
    tcp_thread.join()
    udp_thread.join()
