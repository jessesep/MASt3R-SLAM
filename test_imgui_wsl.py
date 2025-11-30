#!/usr/bin/env python3
"""Test ImGui interactivity on WSL2"""

import imgui
import moderngl_window as mglw
from moderngl_window.integrations.imgui import ModernglWindowRenderer


class TestWindow(mglw.WindowConfig):
    gl_version = (3, 3)
    title = "ImGui WSL2 Test"
    window_size = (800, 600)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        imgui.create_context()
        self.imgui = ModernglWindowRenderer(self.wnd)

        self.checkbox_value = False
        self.slider_value = 0.5
        self.counter = 0

    def render(self, time: float, frametime: float):
        imgui.new_frame()

        io = imgui.get_io()

        # Create a test window
        imgui.begin("Test Controls")
        imgui.text(f"FPS: {io.framerate:.1f}")
        imgui.text(f"Mouse pos: {io.mouse_pos[0]:.0f}, {io.mouse_pos[1]:.0f}")
        imgui.text(f"Want capture mouse: {io.want_capture_mouse}")
        imgui.text(f"Want capture keyboard: {io.want_capture_keyboard}")
        imgui.separator()

        changed, self.checkbox_value = imgui.checkbox("Test Checkbox", self.checkbox_value)
        if changed:
            print(f"Checkbox clicked! New value: {self.checkbox_value}")

        changed, self.slider_value = imgui.slider_float("Test Slider", self.slider_value, 0.0, 1.0)
        if changed:
            print(f"Slider moved! New value: {self.slider_value:.2f}")

        if imgui.button("Click Me!"):
            self.counter += 1
            print(f"Button clicked {self.counter} times!")

        imgui.same_line()
        imgui.text(f"Clicks: {self.counter}")

        imgui.end()

        imgui.render()
        self.imgui.render(imgui.get_draw_data())

    def resize(self, width: int, height: int):
        self.imgui.resize(width, height)

    def key_event(self, key, action, modifiers):
        self.imgui.key_event(key, action, modifiers)

    def mouse_position_event(self, x, y, dx, dy):
        self.imgui.mouse_position_event(x, y, dx, dy)

    def mouse_drag_event(self, x, y, dx, dy):
        self.imgui.mouse_drag_event(x, y, dx, dy)

    def mouse_scroll_event(self, x_offset, y_offset):
        self.imgui.mouse_scroll_event(x_offset, y_offset)

    def mouse_press_event(self, x, y, button):
        print(f"Mouse press at {x}, {y}, button {button}")
        self.imgui.mouse_press_event(x, y, button)

    def mouse_release_event(self, x: int, y: int, button: int):
        print(f"Mouse release at {x}, {y}, button {button}")
        self.imgui.mouse_release_event(x, y, button)

    def unicode_char_entered(self, char):
        self.imgui.unicode_char_entered(char)


if __name__ == "__main__":
    print("Testing ImGui interactivity on WSL2...")
    print("Try clicking the checkbox, moving the slider, and clicking the button")
    print("Watch the terminal for event messages")
    mglw.run_window_config(TestWindow)
