"""Testes de parsing das variáveis SMTP do settings (ERP 4.0.15.x)."""

import os
from unittest.mock import patch

from django.test import SimpleTestCase

from nexus_erp.settings import _email_env_bool, _email_env_int


class EmailEnvParsingTests(SimpleTestCase):
    def test_env_bool_false_variants(self):
        for value in ('False', 'false', '0', 'no', 'off', ''):
            with self.subTest(value=value):
                with patch.dict(os.environ, {'TEST_BOOL': value}, clear=False):
                    self.assertFalse(_email_env_bool('TEST_BOOL', 'False'))

    def test_env_bool_true_variants(self):
        for value in ('1', 'true', 'True', 'yes', 'on', 'ON'):
            with self.subTest(value=value):
                with patch.dict(os.environ, {'TEST_BOOL': value}, clear=False):
                    self.assertTrue(_email_env_bool('TEST_BOOL', 'False'))

    def test_env_int_valid(self):
        with patch.dict(os.environ, {'TEST_PORT': '25'}, clear=False):
            self.assertEqual(_email_env_int('TEST_PORT', '587'), 25)

    def test_env_int_invalid_fallback(self):
        with patch.dict(os.environ, {'TEST_PORT': 'abc'}, clear=False):
            self.assertEqual(_email_env_int('TEST_PORT', '25'), 25)

    def test_env_int_missing_uses_default(self):
        env = os.environ.copy()
        env.pop('TEST_PORT_MISSING', None)
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(_email_env_int('TEST_PORT_MISSING', '25'), 25)
