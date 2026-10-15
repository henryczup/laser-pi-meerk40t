import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from meerk40t.balormk.crs355 import CRS355Controller, calibrated_view
from meerk40t.core.units import Length
from meerk40t.core.view import View


class TestCRS355(unittest.TestCase):
    def controller(self, mock=True):
        c = object.__new__(CRS355Controller)
        c.service = SimpleNamespace(mock=mock, default_frequency=120,
                                    default_power=120, default_speed=500)
        return c

    def test_live_blocked_before_connection_or_initialization(self):
        c = self.controller(False)
        with patch('usb.core.find', side_effect=AssertionError('USB accessed')):
            with self.assertRaises(ConnectionRefusedError):
                c.connect_if_needed()
            with self.assertRaises(ConnectionRefusedError):
                c.init_laser()

    def test_reject_other_recipes_before_writes(self):
        c = self.controller()
        c.frequency = Mock(side_effect=AssertionError('Command sent'))
        for values in ({'frequency': 20}, {'power': 1000}, {'speed': 100}):
            with self.assertRaises(ValueError):
                c.set_settings(values)
        with self.assertRaises(ValueError):
            c._convert_speed(100)
        with self.assertRaises(RuntimeError):
            c.light_mode()

    def test_correction_mismatch_fails_before_command(self):
        c = self.controller()
        c.get_serial_number = Mock(side_effect=AssertionError('Command sent'))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.cor'
            path.write_bytes(b'corrupt')
            c.service.corfile = str(path)
            c.service.crs355_cor_sha256 = hashlib.sha256(b'expected').hexdigest()
            with self.assertRaises(ValueError):
                c.init_laser()

    def test_scale_required_and_center_mapping(self):
        v = View('200mm', '200mm',
                 native_scale_x=float(Length('200mm'))/65535,
                 native_scale_y=float(Length('200mm'))/65535)
        for value in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                calibrated_view(v, value, 1)
        calibrated_view(v, 1, 1)
        self.assertEqual(tuple(round(x) for x in v.position('100mm', '100mm')),
                         (32768, 32768))

    def test_device_selection_is_opt_in(self):
        from test.bootstrap import bootstrap
        from meerk40t.balormk.device import BalorDevice
        from meerk40t.balormk.controller import GalvoController
        kernel = bootstrap()
        try:
            stock = BalorDevice(kernel, 'stock-test')
            self.assertIs(type(stock.driver.connection), GalvoController)
            values = dict(crs355_profile=True, source='uv', mock=True,
                          lens_size='200mm', crs355_scale_x=1., crs355_scale_y=1.)
            custom = BalorDevice(kernel, 'crs-test', choices=[
                {'attr': key, 'default': value} for key, value in values.items()])
            self.assertIsInstance(custom.driver.connection, CRS355Controller)
            custom.mock = False
            with self.assertRaises(ValueError):
                custom.realize()
        finally:
            kernel()


if __name__ == '__main__':
    unittest.main()
