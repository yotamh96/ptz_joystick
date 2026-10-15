import unittest
from dataclasses import fields, replace

from ptz_joystick.app.checks import type_error
from ptz_joystick.config import Settings
from ptz_joystick.core.commands import Preset, Tracking
from ptz_joystick.windows.settings_dialog import form

PW = replace(Settings(), password="pw")


def save(**changes):
    """from_fields on the default fields, with some changed as the operator would type them."""
    return form.from_fields({**form.to_fields(PW), **changes}, type_error)


class FieldsTest(unittest.TestCase):
    def test_every_setting_has_a_field_on_a_tab(self):
        self.assertEqual({f.setting for f in form.FIELDS}, {f.name for f in fields(Settings)})
        self.assertLessEqual({f.tab for f in form.FIELDS}, set(form.TABS))

    def test_fields_give_the_same_settings_back(self):
        s = replace(Settings(), host="http://10.0.0.9", password='p"w', controller="keyboard", invert_zoom=False,
                    deadzone=0.1, timeout=2.0, log_file="", buttons={0: Preset(1), 5: Tracking(True), 20: Preset(30)})
        self.assertEqual(form.from_fields(form.to_fields(s), type_error), s)

    def test_twelve_button_rows_or_up_to_the_highest(self):
        self.assertEqual(len(form.to_fields(PW)["buttons"]), 12)
        rows = form.to_fields(replace(PW, buttons={31: Preset(2)}))["buttons"]
        self.assertEqual((len(rows), rows[31], rows[0]), (32, ("preset", "2"), ("nothing", "")))
        self.assertEqual(save(buttons=rows).buttons, {31: Preset(2)})

    def test_a_tracking_row_ignores_its_number_box(self):
        rows = form.to_fields(PW)["buttons"]
        rows[4] = ("tracking", "7")
        self.assertEqual(save(buttons=rows).buttons[4], Tracking(True))

    def test_spaces_around_a_number_are_fine(self):
        self.assertEqual(save(pan_max=" 12 ", deadzone="0.2 ").pan_max, 12)

    def test_spaces_around_a_pasted_address_are_dropped_but_the_password_is_as_typed(self):
        s = save(host=" http://10.0.0.9 ", user="admin ", password=" p w ")
        self.assertEqual((s.host, s.user, s.password), ("http://10.0.0.9", "admin", " p w "))

    def test_only_preset_takes_a_number(self):
        self.assertEqual([a for a in form.ACTIONS if form.numbered(a)], ["preset"])


class ErrorTest(unittest.TestCase):
    CASES = (               # (field, what the operator typed, the field that gets marked)
        ("host", "192.168.77.3", "host"),
        ("timeout", "3", "timeout"),
        ("timeout", "abc", "timeout"),
        ("pan_axis", "Q", "pan_axis"),
        ("deadzone", "0.8", "deadzone"),
        ("deadzone", "0,15", "deadzone"),
        ("full_speed_at", "1.5", "deadzone"),       # the rule names both: the first is marked (spec)
        ("pan_max", "0", "pan_max"),
        ("pan_max", "2.5", "pan_max"),
        ("tilt_max", "21", "tilt_max"),             # over the camera's ceiling: type_error
        ("save_hold_seconds", "11", "save_hold_seconds"),
        ("camera", "sony", "camera"),
        ("controller", "xbox", "controller"),
    )

    def test_every_rule_marks_its_field(self):
        for setting, text, marked in self.CASES:
            with self.subTest(setting=setting, text=text):
                with self.assertRaises(form.FieldError) as cm:
                    save(**{setting: text})
                self.assertEqual(cm.exception.setting, marked, cm.exception.message)

    def test_a_comma_decimal_is_named_in_the_usual_words(self):
        with self.assertRaises(form.FieldError) as cm:
            save(deadzone="0,15")
        self.assertEqual(cm.exception.message, "deadzone must be a number, got '0,15'")

    def test_a_bad_preset_row_names_its_row(self):
        rows = form.to_fields(PW)["buttons"]
        rows[2] = ("preset", "x")
        with self.assertRaises(form.FieldError) as cm:
            save(buttons=rows)
        self.assertEqual((cm.exception.setting, cm.exception.row), ("buttons", 2))
        self.assertTrue(cm.exception.message.startswith("button 3: bad command 'preset x'"), cm.exception.message)

    def test_an_empty_password_is_refused(self):
        with self.assertRaises(form.FieldError) as cm:
            save(password="")
        self.assertEqual((cm.exception.setting, cm.exception.message), ("password", "The camera password is not set"))


if __name__ == "__main__":
    unittest.main()
