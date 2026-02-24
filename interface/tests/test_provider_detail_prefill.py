from django.test import TestCase

from interface.views import _first_form_error


class FirstFormErrorTests(TestCase):
    def test_returns_none_when_form_has_no_errors(self):
        class Form:
            def non_field_errors(self):
                return []
            errors = {}

        self.assertIsNone(_first_form_error(Form()))
