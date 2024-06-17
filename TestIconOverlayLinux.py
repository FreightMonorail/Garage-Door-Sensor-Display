# /home/pi/json_monitor_overlay.py

import socket
import json
import sys
import os
import time
import signal
import selectors
from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QShortcut
from PyQt5.QtGui import QPixmap, QPainter, QKeySequence
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal

TIMEOUT_TIME = 1205 # The amount of time (in seconds) that can elapse before we start to worry about not having heard from the sensor
WINDOW_SIZE = 200
WINDOW_DIMENSIONS = (WINDOW_SIZE, WINDOW_SIZE)

timeout_exp = time.time() # If the time ever goes beyond this timeout, it has been too long since we last heard form the sensor
window = None

class TimeoutWatcher(QThread):

    def __init__(self) -> None:
        super().__init__()
        self.running = True

    def run(self) -> None:
        while self.running:
            global timeout_exp
            if time.time() > timeout_exp: # If it has been too long since we got a reading, display the error icon
                timeout_exp = time.time() + TIMEOUT_TIME # Add seconds to the timeout
                window.change_image(garageUnknown, WINDOW_SIZE, WINDOW_SIZE)

    def stop(self):
        self.running = False

class SocketListener(QThread):
    data_received = pyqtSignal(str)

    def __init__(self, port):
        super().__init__()
        self.port = port
        self.running = True

    def run(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(('0.0.0.0', self.port))
        server_socket.listen(1)
        print(f'Server listening on port {self.port}...')

        while self.running:
            client_socket, addr = server_socket.accept()
            data = client_socket.recv(1024).decode('utf-8')
            if data:
                self.data_received.emit(data)
                # Send a 200 OK response to the clientresponse_body = json.dumps({"status": "success", "who_updated": 1})
                body = "{\"status\": \"success\", \"who_updated\": 1}"
                response = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n{body}"
                client_socket.send(response.encode('utf-8'))
            client_socket.close()

    def stop(self):
        self.running = False


class TransparentWindow(QWidget):
    def __init__(self, image_path, new_width=None, new_height=None):
        super().__init__()

        # Load the image
        self.image = QPixmap(image_path)

        # Get display dimensions
        screen_geometry = QApplication.desktop().screenGeometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        initial_x = (screen_width - WINDOW_SIZE) - 10
        initial_y = (screen_height - WINDOW_SIZE) - 30

        print(f"Screen width: {screen_width}, height: {screen_height}")
        print(f"initial_x: {initial_x}, initial_y: {initial_y}")

        # Resize the image if new dimensions are provided
        if new_width and new_height:
            self.image = self.image.scaled(new_width, new_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        # Set the window properties
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.X11BypassWindowManagerHint | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setGeometry(initial_x, initial_y, self.image.width(), self.image.height())
        self.setWindowOpacity(0.9)  # Set the window opacity

        # Create a label to display the image
        self.label = QLabel(self)
        self.label.setPixmap(self.image)
        self.label.setGeometry(0, 0, self.image.width(), self.image.height())

        # Add a shortcut to close the window
        close_shortcut = QShortcut(QKeySequence("Escape"), self)
        close_shortcut.activated.connect(self.close)

    def change_image(self, new_image_path, new_width=None, new_height=None):
        # Load the new image
        new_image = QPixmap(new_image_path)

        # Resize the new image if new dimensions are provided
        if new_width and new_height:
            new_image = new_image.scaled(new_width, new_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        # Update the label with the new image
        self.label.setPixmap(new_image)
        self.label.setGeometry(0, 0, new_image.width(), new_image.height())

        # Resize the window to fit the new image
        self.setGeometry(self.x(), self.y(), new_image.width(), new_image.height())

        # Update the internal image reference
        self.image = new_image

    def update_image_from_data(self, data):
        try:
            # Extract the body of the HTTP request
            # strData = data.decode('utf-8')
            headers, body = data.split('\r\n\r\n', 1)
            # Parse the JSON data
            json_data = json.loads(body)
            sensors = json_data.get('sensors', False)
            
            value = False
            
            # Display appropriate icon based on the value
            if sensors:
                value = float(json_data["sensors"][0]["samples"][-1]["v"])

                if value > 1:
                    self.change_image(garageOpen, WINDOW_SIZE, WINDOW_SIZE)
                else:
                    self.change_image(garageClosed, WINDOW_SIZE, WINDOW_SIZE)

                global timeout_exp
                timeout_exp = time.time() + TIMEOUT_TIME # Add seconds to the timeout
                print(f"Extracted value: {value}")
            
        except json.JSONDecodeError:
            pass

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setOpacity(1.0)  # Ensure the image is fully opaque
        painter.drawPixmap(0, 0, self.image)

def sigint_handler(*args):
    """Handler for the SIGINT signal."""
    sys.stderr.write('\r')
    print("Terminated")
    sys.exit()

# Load icons
garageOpen = 'Images/GarageOpen.png'
garageClosed = 'Images/GarageClosed.png'
garageUnknown = 'Images/GarageUnknown.png'

def main():
    signal.signal(signal.SIGINT, sigint_handler)
    global window
    app = QApplication(sys.argv)
    window = TransparentWindow(garageUnknown, WINDOW_SIZE, WINDOW_SIZE)
    window.show()
    
    # Set up the socket listener
    listener = SocketListener(port=55257)
    listener.data_received.connect(window.update_image_from_data)
    listener.start()

    timeout = TimeoutWatcher()
    timeout.start()

    # Clean up on exit
    def cleanup():
        listener.stop()
        listener.wait()
        timeout.stop()
        timeout.wait()
        
    app.aboutToQuit.connect(cleanup)

    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(100)

    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
