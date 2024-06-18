# /home/pi/json_monitor_overlay.py

import socket
import json
import sys
import ctypes
import os
import time
import selectors
import win32gui
import win32con
import pygame

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_LAYERED = 0x80000
WS_EX_TRANSPARENT = 0x20
TIMEOUT_TIME = 20 # The amount of time (in seconds) that can elapse before we start to worry about not having heard from the sensor

timeout_exp = time.time() # If the timeever goes beyond this timeout, it has been too long since we last heard form the sensor

def set_window_exstyle(hwnd, exstyle):
    current_exstyle = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, current_exstyle | exstyle)


pygame.init()

window_size = 100
window_dimensions = (window_size, window_size)

# Get the screen width and height
screen_width, screen_height = pygame.display.Info().current_w, pygame.display.Info().current_h

# Calculate the initial position based on screen width and height
initial_x = (screen_width - window_size) - 10
initial_y = (screen_height - window_size) - 30

# Set the initial position
os.environ['SDL_VIDEO_WINDOW_POS'] = f"{initial_x},{initial_y}"

# Initialize Pygame
screen = pygame.display.set_mode(window_dimensions, pygame.NOFRAME)
pygame.display.set_caption('Overlay')

hwnd = pygame.display.get_wm_info()["window"]
ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref((ctypes.c_int * 4)(-1, -1, -1, -1)))

# Set the window style to remove it from the taskbar and make it a click-through, so you can click behind it.
set_window_exstyle(hwnd, (WS_EX_TOOLWINDOW | WS_EX_LAYERED | WS_EX_TRANSPARENT))
ctypes.windll.user32.ShowWindow(hwnd, 1)  # Force the window to show (in case it was hidden)

# Set the window always on top
win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)

# Load icons
happyPlant = pygame.transform.scale(pygame.image.load('Images/PlantHappy.png'), window_dimensions)
sadPlant = pygame.transform.scale(pygame.image.load('Images/PlantSad.png'), window_dimensions)
deadPlant = pygame.transform.scale(pygame.image.load('Images/PlantDead.png'), window_dimensions)
errorPlant = pygame.transform.scale(pygame.image.load('Images/Error.png'), window_dimensions)

transparent_color = pygame.Color(0, 0, 0, 0)

# Initialize the selector
sel = selectors.DefaultSelector()

def accept(sock):
    try:
        conn, addr = sock.accept()
        print(f'Accepted connection from {addr}')
        conn.setblocking(False)
        sel.register(conn, selectors.EVENT_READ, read)
    except Exception as e:
        print(f'Error accepting connection: {e}')
    
def read(conn):
    try:
        request_data = conn.recv(1024)
        print(f'Received data: {request_data}\r\n\r\n')
        response_body = handle_request(request_data)
        response = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: application/json\r\n"
            "Content-Length: {}\r\n"
            "Connection: close\r\n"
            "\r\n"
            "{}"
        ).format(len(response_body), response_body)
        conn.sendall(response.encode('utf-8'))
        
    except json.JSONDecodeError as e:
        print(f'Error decoding JSON: {e}')

    except Exception as e:
        print(f'Error: {e}')

    finally:
        sel.unregister(conn)
        conn.close()

def handle_request(data):
    try:
        # Extract the body of the HTTP request
        headers, body = data.split(b'\r\n\r\n', 1)
        # Parse the JSON data
        json_data = json.loads(body.decode('utf-8'))
        # Extract a value from the JSON data (example: "value" key)
        
        json_data = json.loads(body)
        sensors = json_data.get('sensors', False)
        
        value = False
        
        # Display appropriate icon based on the value
        if sensors:
            value = float(json_data["sensors"][0]["samples"][-1]["v"])
            screen.fill(transparent_color)
            if value < 0.2:
                screen.blit(deadPlant, (0, 0))
            elif value < 1:
                screen.blit(sadPlant, (0, 0))    
            else:
                screen.blit(happyPlant, (0, 0))
            
            pygame.display.update()
            global timeout_exp
            timeout_exp = time.time() + TIMEOUT_TIME # Add seconds to the timeout
            print(f"Extracted value: {value}")
        # Create a response body with the extracted value
        response_body = json.dumps({"status": "success", "who_updated": 1})
    except Exception as e:
        print(f"Error parsing JSON: {e}")
        response_body = json.dumps({"status": "error", "who_updated": 1})
    return response_body
    

def server_runner():
    # Set up server
    host = '0.0.0.0'
    port = 55257
            
    pygame.display.update()
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen()
    server_socket.setblocking(False)
    sel.register(server_socket, selectors.EVENT_READ, accept)
    
    print(f'Server listening on port {port}...')

    while True:
        # Handle pygame events to allow quitting
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left mouse button
                    print("Left mouse button clicked")
                    screen.fill(transparent_color)
                    pygame.display.update()
                elif event.button == 3:  # Right mouse button
                    print("Right mouse button clicked")
                    pygame.quit()
                    sys.exit()
                    
        global timeout_exp
        if time.time() > timeout_exp: # If it has been too long since we got a reading, display the error icon
            timeout_exp = time.time() + TIMEOUT_TIME # Add seconds to the timeout
            screen.fill(transparent_color)
            screen.blit(errorPlant, (0, 0))
            pygame.display.update()
        
        events = sel.select(timeout=1)
        for key, mask in events:
            callback = key.data
            callback(key.fileobj)
            
        time.sleep(1)  # If you don't have this, it eats CPU like crazy.
                     
if __name__ == '__main__':
    server_runner()
