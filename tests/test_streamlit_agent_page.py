import unittest

from streamlit.testing.v1 import AppTest


class StreamlitAgentPageTests(unittest.TestCase):
    def test_page_renders_and_enables_agent_for_requirement_input(self):
        app = AppTest.from_file("main.py").run(timeout=10)

        self.assertFalse(app.exception)
        self.assertEqual(len(app.text_area), 1)
        self.assertEqual(len(app.button), 2)
        self.assertTrue(app.button[0].disabled)

        app.text_area[0].set_value("用户可以提交订单")
        app.run(timeout=10)

        self.assertFalse(app.exception)
        self.assertFalse(app.button[0].disabled)


if __name__ == "__main__":
    unittest.main()
