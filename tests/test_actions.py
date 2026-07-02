import unittest

import local_rpa_agent.actions as actions
from local_rpa_agent.actions import LocalActions


class FakePyAutoGUI:
    def __init__(self):
        self.calls = []

    def hotkey(self, *keys):
        self.calls.append(('hotkey', keys))

    def press(self, key):
        self.calls.append(('press', key))

    def write(self, text):
        self.calls.append(('write', text))


class ActionTest(unittest.TestCase):
    def test_type_text_replace_clears_current_input_before_typing(self):
        fake = FakePyAutoGUI()
        old_pyautogui = actions.pyautogui
        old_pyperclip = actions.pyperclip
        try:
            actions.pyautogui = fake
            actions.pyperclip = None

            result = LocalActions().type_text({'input_mode': 'replace'}, 'AC0194')

            self.assertTrue(result.ok)
            self.assertEqual(fake.calls[:3], [('hotkey', ('ctrl', 'a')), ('press', 'backspace'), ('write', 'AC0194')])
        finally:
            actions.pyautogui = old_pyautogui
            actions.pyperclip = old_pyperclip

    def test_type_text_append_does_not_clear_current_input(self):
        fake = FakePyAutoGUI()
        old_pyautogui = actions.pyautogui
        old_pyperclip = actions.pyperclip
        try:
            actions.pyautogui = fake
            actions.pyperclip = None

            result = LocalActions().type_text({'input_mode': 'append'}, '-tail')

            self.assertTrue(result.ok)
            self.assertEqual(fake.calls, [('write', '-tail')])
        finally:
            actions.pyautogui = old_pyautogui
            actions.pyperclip = old_pyperclip

    def test_upload_file_accepts_rendered_list_paths(self):
        fake = FakePyAutoGUI()
        old_pyautogui = actions.pyautogui
        old_pyperclip = actions.pyperclip
        try:
            actions.pyautogui = fake
            actions.pyperclip = None

            result = LocalActions().upload_file({'allow_missing': True}, ['C:\\tmp\\a.jpg', 'C:\\tmp\\b.jpg'])

            self.assertTrue(result.ok)
            self.assertEqual(fake.calls, [('write', '"C:\\tmp\\a.jpg" "C:\\tmp\\b.jpg"'), ('press', 'enter')])
        finally:
            actions.pyautogui = old_pyautogui
            actions.pyperclip = old_pyperclip


if __name__ == '__main__':
    unittest.main()
