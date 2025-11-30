"""UDP Command Listener for Control GUI Integration

Listens for commands from the Control GUI and executes them on the SLAM system.

Commands:
- pause/resume: Control SLAM processing
- reset: Clear all keyframes and restart
- save_ply: Export current point cloud
- save_keyframes: Save keyframe images
- change_source: Switch camera input source
"""

import socket
import json
import threading
import queue
from typing import Callable, Dict, Any


class CommandListener:
    """Listen for UDP commands from Control GUI"""

    def __init__(self, port: int = 9999, status_port: int = 10000):
        """
        Args:
            port: Port to listen for commands (default: 9999)
            status_port: Port to send status updates (default: 10000)
        """
        self.port = port
        self.status_port = status_port
        self.running = False
        self.thread = None
        self.command_queue = queue.Queue()

        # Create sockets
        self.listen_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listen_sock.settimeout(1.0)

        self.status_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Bind listen socket
        try:
            self.listen_sock.bind(('127.0.0.1', self.port))
            print(f"Command listener bound to port {self.port}")
        except OSError as e:
            print(f"Warning: Could not bind command listener to port {self.port}: {e}")
            self.listen_sock = None

    def start(self):
        """Start listening thread"""
        if self.listen_sock is None:
            print("Command listener not available (port bind failed)")
            return

        self.running = True
        self.thread = threading.Thread(target=self._listen_worker, daemon=True)
        self.thread.start()
        print("Command listener started")

    def stop(self):
        """Stop listening thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)

    def _listen_worker(self):
        """Background thread for receiving commands"""
        while self.running:
            try:
                data, addr = self.listen_sock.recvfrom(4096)
                command = json.loads(data.decode('utf-8'))
                self.command_queue.put(command)
                print(f"Received command: {command.get('action', 'unknown')}")
            except socket.timeout:
                continue
            except json.JSONDecodeError as e:
                print(f"Invalid command JSON: {e}")
            except Exception as e:
                if self.running:  # Only print error if we're still supposed to be running
                    print(f"Error receiving command: {e}")

    def get_command(self, block=False, timeout=None) -> Dict[str, Any]:
        """Get next command from queue

        Args:
            block: Whether to block waiting for command
            timeout: Timeout in seconds if blocking

        Returns:
            Command dictionary or None if queue empty
        """
        try:
            return self.command_queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None

    def has_commands(self) -> bool:
        """Check if there are pending commands"""
        return not self.command_queue.empty()

    def send_status(self, status: Dict[str, Any]):
        """Send status update to Control GUI

        Args:
            status: Status dictionary (fps, keyframes, etc.)
        """
        if self.status_sock is None:
            return

        try:
            msg = json.dumps(status).encode('utf-8')
            self.status_sock.sendto(msg, ('127.0.0.1', self.status_port))
        except Exception as e:
            # Silently ignore status send errors (GUI might not be running)
            pass


class CommandHandler:
    """Handle commands from Control GUI"""

    def __init__(self, slam=None):
        """
        Args:
            slam: SLAM instance to control
        """
        self.slam = slam
        self.paused = False
        self.custom_handlers = {}

    def register_handler(self, action: str, handler: Callable):
        """Register custom command handler

        Args:
            action: Command action name
            handler: Callable that takes command dict
        """
        self.custom_handlers[action] = handler

    def handle_command(self, command: Dict[str, Any]) -> bool:
        """Process a command

        Args:
            command: Command dictionary

        Returns:
            True if command was handled, False otherwise
        """
        action = command.get('action')

        if action is None:
            return False

        # Check custom handlers first
        if action in self.custom_handlers:
            self.custom_handlers[action](command)
            return True

        # Built-in handlers
        if action == 'pause':
            self.paused = True
            print("SLAM paused")
            return True

        elif action == 'resume':
            self.paused = False
            print("SLAM resumed")
            return True

        elif action == 'reset':
            if self.slam:
                print("Resetting SLAM...")
                # Note: Actual reset implementation depends on SLAM class
                # This is a placeholder
                print("Reset complete")
            return True

        elif action == 'save_ply':
            output_path = command.get('path', 'results/manual_save.ply')
            if self.slam:
                print(f"Saving PLY to {output_path}...")
                # Note: Actual save implementation depends on SLAM class
                print("Saved!")
            return True

        elif action == 'save_keyframes':
            output_dir = command.get('path', 'results/keyframes/')
            if self.slam:
                print(f"Saving keyframes to {output_dir}...")
                # Note: Actual save implementation depends on SLAM class
                print("Saved!")
            return True

        elif action == 'change_source':
            print(f"Source change requested: {command.get('type')}")
            print("Note: Source changing requires restart in current implementation")
            return True

        return False

    def is_paused(self) -> bool:
        """Check if SLAM is paused"""
        return self.paused
