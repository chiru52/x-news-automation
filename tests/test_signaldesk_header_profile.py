"""Header appearance and truthful guest-account entry points."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class HeaderAccountTests(unittest.TestCase):
    def test_theme_icons_and_guest_menu(self):
        html=(ROOT/"dashboard/index.html").read_text()
        js=(ROOT/"dashboard/app.js").read_text()
        self.assertIn('id="theme-toggle"',html)
        self.assertIn('class="theme-sun"',html)
        self.assertIn('class="theme-moon"',html)
        self.assertIn('id="profile-toggle"',html)
        self.assertIn('aria-expanded="false"',html)
        self.assertIn('./account.html#sign-in',html)
        self.assertIn('./account.html#sign-up',html)
        self.assertIn('signaldesk:theme:v1',js)
        self.assertIn('setProfileOpen(false)',js)
    def test_auth_not_faked_and_exported(self):
        page=(ROOT/"dashboard/account.html").read_text()
        export=(ROOT/"newsbot/dashboard_export.py").read_text()
        self.assertIn("not available yet",page)
        self.assertNotIn('type="password"',page)
        self.assertIn('"account.html"',export)
if __name__=="__main__": unittest.main()
