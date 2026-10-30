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
        self.assertIn('updateOptionalAccountProfile()',js)
        self.assertIn('if(config.enabled!==true) return;',js)
        self.assertIn('auth.auth.getUser()',js)
        self.assertIn('signIn.hidden=signedIn',js)
        self.assertIn('id="profile-account-link" hidden',html)
    def test_auth_not_faked_and_exported(self):
        page=(ROOT/"dashboard/account.html").read_text()
        export=(ROOT/"newsbot/dashboard_export.py").read_text()
        self.assertIn('id="auth-form" hidden',page)
        self.assertIn('type="password"',page)
        self.assertIn('"account.html"',export)
        self.assertIn('"account.mjs"',export)
        self.assertIn('"auth-config.json"',export)
        config=(ROOT/"dashboard/auth-config.json").read_text()
        self.assertIn('"enabled":false',config)
        client=(ROOT/"dashboard/account.mjs").read_text()
        self.assertIn("signInWithPassword",client)
        self.assertIn("signUp",client)
        self.assertIn("resetPasswordForEmail",client)
        self.assertIn("updateUser",client)
        self.assertNotIn("service_role",config)
        self.assertIn('recoveryAuthorized=false',client)
        self.assertIn('event==="PASSWORD_RECOVERY"',client)
        self.assertIn('mode==="update-password" && !recoveryAuthorized',client)
        self.assertIn('previousElementSibling.hidden=mode==="update-password"',client)
if __name__=="__main__": unittest.main()
