import socket
import threading
import json
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController

# --- Configuration ---
HOST = '0.0.0.0'
TCP_PORT = 5000       # For reliable commands (Clicks, Keystrokes)
UDP_PORT = 5001       # For fast commands (Mouse Movement, Scroll)
BUFFER_SIZE = 1024 

# --- Controllers for Input Injection ---
mouse = MouseController()
keyboard = KeyboardController()

# --- Command Handling Functions (Same as before, but called from different sockets) ---

def handle_input(data):
    """Parses data and calls the appropriate handler."""
    if 'category' in data:
        if data['category'] == 'mouse':
            if data['type'] in ('move', 'scroll'):
                # Handle move/scroll immediately and fast (UDP)
                if data['type'] == 'move':
                    mouse.move(data.get('dx', 0), data.get('dy', 0))
                elif data['type'] == 'scroll':
                    mouse.scroll(0, data.get('dy', 0))
                return f"[FAST] Mouse {data['type']}"
            
            elif data['type'] == 'click':
                # Handle click reliably (TCP)
                button_str = data.get('button', 'left').lower()
                button = Button.left if button_str == 'left' else Button.right
                mouse.click(button, 1)
                return f"[RELIABLE] Mouse click: {button_str}"

        elif data['category'] == 'keyboard':
            # Handle keyboard reliably (TCP)
            if data['type'] == 'char':
                keyboard.type(data.get('char', ''))
                return f"[RELIABLE] Typed: '{data.get('char')}'"
            
            elif data['type'] == 'key':
                key_map = {'enter': Key.enter, 'space': Key.space, 'backspace': Key.backspace}
                pynput_key = key_map.get(data.get('key').lower())
                if pynput_key:
                    keyboard.press(pynput_key)
                    keyboard.release(pynput_key)
                    return f"[RELIABLE] Pressed key: {data.get('key')}"
    return "[ERROR] Unknown command"


# ----------------------------------------------------------------------
## UDP Listener (Handles high-frequency, non-critical movement)
# ----------------------------------------------------------------------

def udp_listener():
    """Listens for fast mouse movement/scroll commands via UDP."""
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind((HOST, UDP_PORT))
    print(f"UDP Listener started on port {UDP_PORT}")
    
    while True:
        try:
            data_bytes, addr = udp_socket.recvfrom(BUFFER_SIZE)
            message = data_bytes.decode('utf-8').strip()
            
            # Note: We expect UDP packets to be single, complete JSON objects
            data = json.loads(message)
            result = handle_input(data)
            # Print only movement to avoid flooding console
            if 'move' in result: 
                print(f"{result}") 
                
        except Exception as e:
            # UDP is unreliable, so errors here are often acceptable drops/noise
            # print(f"UDP error: {e}") 
            pass


# ----------------------------------------------------------------------
## TCP Listener (Handles connection, reliable clicks, and keystrokes)
# ----------------------------------------------------------------------

def tcp_client_handler(conn, addr):
    """Handles reliable commands from a single TCP client."""
    data_buffer = ""
    print(f"\n[TCP] Client connected: {addr}")
    
    try:
        while True:
            data_chunk = conn.recv(BUFFER_SIZE).decode('utf-8')
            if not data_chunk:
                break

            data_buffer += data_chunk
            
            # Process complete JSON messages separated by '\n'
            while '\n' in data_buffer:
                message, data_buffer = data_buffer.split('\n', 1)
                
                if not message.strip(): continue

                try:
                    data = json.loads(message)
                    result = handle_input(data)
                    # Print all reliable commands
                    if '[RELIABLE]' in result:
                         print(result)

                except json.JSONDecodeError:
                    print(f"[TCP ERROR] Invalid JSON: {message}")
                
    finally:
        print(f"[TCP] Connection closed from {addr}")
        conn.close()


def tcp_listener():
    """Sets up and starts the TCP server."""
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        tcp_socket.bind((HOST, TCP_PORT))
        tcp_socket.listen(5)
        print(f"TCP Listener started on port {TCP_PORT}")
        
        while True:
            conn, addr = tcp_socket.accept()
            # Start a new thread for each client connection
            threading.Thread(target=tcp_client_handler, args=(conn, addr), daemon=True).start()

    except socket.error as e:
        print(f"Failed to start TCP listener on {HOST}:{TCP_PORT}. Error: {e}")

# ----------------------------------------------------------------------
## Main Server Startup
# ----------------------------------------------------------------------

if __name__ == '__main__':
    print("--------------------------------------------------")
    print(f" 🚀 Hybrid Input Server Starting...")
    print(f" Host IP: {socket.gethostbyname(socket.gethostname())}")
    print(" Press Ctrl+C to stop.")
    print("--------------------------------------------------")
    
    # Start both listeners in separate threads
    tcp_thread = threading.Thread(target=tcp_listener, daemon=True)
    udp_thread = threading.Thread(target=udp_listener, daemon=True)
    
    tcp_thread.start()
    udp_thread.start()

    try:
        # Keep the main thread alive
        while True:
            threading.Event().wait(1) 
    except KeyboardInterrupt:
        print("\n[STOPPED] Server shutting down.")