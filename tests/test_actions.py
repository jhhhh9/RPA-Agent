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

    def click(self, x, y, duration=0):
        self.calls.append(('click', x, y, duration))


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

    def test_upload_file_one_by_one_uploads_each_path_separately(self):
        fake = FakePyAutoGUI()
        old_pyautogui = actions.pyautogui
        old_pyperclip = actions.pyperclip
        try:
            actions.pyautogui = fake
            actions.pyperclip = None

            result = LocalActions().upload_file(
                {'allow_missing': True, 'upload_mode': 'one_by_one'},
                ['C:\\tmp\\a.pdf', 'C:\\tmp\\b.pdf'],
            )

            self.assertTrue(result.ok)
            self.assertEqual(fake.calls, [
                ('write', '"C:\\tmp\\a.pdf"'),
                ('press', 'enter'),
                ('write', '"C:\\tmp\\b.pdf"'),
                ('press', 'enter'),
            ])
            self.assertIn('uploaded 2 file(s)', result.message)
        finally:
            actions.pyautogui = old_pyautogui
            actions.pyperclip = old_pyperclip

    def test_optional_click_skips_when_coordinate_is_empty(self):
        fake = FakePyAutoGUI()
        old_pyautogui = actions.pyautogui
        try:
            actions.pyautogui = fake

            result = LocalActions().optional_click({'strategy': 'coordinate_click_twice', 'x': 0, 'y': 0})

            self.assertTrue(result.ok)
            self.assertIn('skipped', result.message)
            self.assertEqual(fake.calls, [])
        finally:
            actions.pyautogui = old_pyautogui

    def test_optional_click_skips_when_guard_value_is_empty(self):
        fake = FakePyAutoGUI()
        old_pyautogui = actions.pyautogui
        try:
            actions.pyautogui = fake

            result = LocalActions().optional_click({
                'strategy': 'coordinate_click_twice',
                'x': 1057,
                'y': 610,
                'guard_value': '',
            })

            self.assertTrue(result.ok)
            self.assertIn('guard', result.message)
            self.assertEqual(fake.calls, [])
        finally:
            actions.pyautogui = old_pyautogui

    def test_optional_click_coordinate_clicks_twice_when_configured(self):
        fake = FakePyAutoGUI()
        old_pyautogui = actions.pyautogui
        try:
            actions.pyautogui = fake

            result = LocalActions().optional_click({'strategy': 'coordinate_click_twice', 'x': 1057, 'y': 610})

            self.assertTrue(result.ok)
            self.assertEqual(fake.calls, [('click', 1057, 610, 0.12), ('click', 1057, 610, 0.12)])
        finally:
            actions.pyautogui = old_pyautogui


if __name__ == '__main__':
    unittest.main()
