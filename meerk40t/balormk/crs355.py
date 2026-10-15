"""Opt-in CRS-355-5 captured recipe. General output remains simulation-only."""
from pathlib import Path
import hashlib
import math
from meerk40t.balormk import controller as bc

INITIALIZE_AFTER_COR=[(4,), (0x16,0),(0x1b,1),(0x17,1),(0x1c,1),
                     (0x1d,2000,20,1),(0x1a,200),(0x1e,3),(6,3),
                     (0x23,0),(0x32,0,82,1000,24),(0x3a,0),
                     (0x21,0),(0x22,3275),(0x0d,32768,32768)]

def calibrated_view(view, scale_x, scale_y):
    SX, SY = float(scale_x), float(scale_y)
    if not all(math.isfinite(s) and 0 < s <= 2 for s in (SX, SY)):
        raise ValueError("Explicit, validated CRS calibration scales are required.")
    view.transform(user_scale_x=SX,user_scale_y=SY,swap_xy=True)
    view.origin(-(32768-SY*32767.5)/65535,-(32768-SX*32767.5)/65535)

class CRS355Controller(bc.GalvoController):
    def connect_if_needed(self):
        if not self.service.mock:
            raise ConnectionRefusedError('Henry UV adapter is simulation-only pending physical validation.')
        return super().connect_if_needed()

    def init_laser(self):
        if not self.service.mock:
            raise ConnectionRefusedError('Live initialization has not been validated.')
        correction = Path(self.service.corfile)
        expected = self.service.crs355_cor_sha256
        if len(expected) != 64 or hashlib.sha256(correction.read_bytes()).hexdigest() != expected:
            raise ValueError("CRS correction file does not match its configured SHA256.")
        self.get_serial_number()
        self.get_version()
        # Exact initialization sequence from the hardware-blocked LightBurn capture.
        self._command(3)
        self.write_correction_file(str(correction))
        for command in INITIALIZE_AFTER_COR:
            self._command(*command)

    def _convert_speed(self,speed):
        # Only these exact settings were observed. Do not extrapolate.
        if float(speed)==500:return 188
        if float(speed)==4000:return 1508
        raise ValueError('This verified recipe supports marking500 and travel4000 mm/s only.')

    def program_mode(self):
        if self.mode==bc.DRIVER_STATE_PROGRAM:return
        if self.mode==bc.DRIVER_STATE_LIGHT:raise RuntimeError('Framing transition not validated.')
        self.reset_list()
        self._port_bits=0
        self.write_port()
        self.mode=bc.DRIVER_STATE_PROGRAM
        for name in ('_ready','_speed','_travel_speed','_frequency','_power','_pulse_width',
                     '_delay_jump','_delay_on','_delay_off','_delay_poly','_delay_end','_fpk'):
            setattr(self,name,None)
        self.list_ready()

    def execute_list(self):
        result=super().execute_list()
        self.set_control_mode(1)
        self._command(0x1d,2000,20,1)
        self._port_bits=0
        self.write_port()
        return result

    def light_mode(self):
        raise RuntimeError('Red-light framing is not enabled in this simulation candidate.')

    def set_settings(self,settings):
        frequency=float(settings.get('frequency',self.service.default_frequency))
        power=float(settings.get('power',self.service.default_power))/10
        speed=float(settings.get('speed',self.service.default_speed))
        if (frequency,power,speed)!=(120,12,500):
            raise ValueError(f'Validated recipe: 120kHz, UV duty12% (internal power120), speed500mm/s. Received frequency={frequency}, duty={power}, speed={speed}.')
        self.frequency(frequency);self.fpk(10);self.power(power)
        self.list_jump_speed(4000);self.list_mark_speed(500)
        self.list_laser_on_delay(100);self.list_laser_off_delay(100)
        self.list_polygon_delay(100)

    def list_jump(self,x,y,short=None,long=None,distance_limit=None):
        # Stock vector driver omits these arguments. Apply the profile's
        # 200/400us delays, converting to the controller's 10us units.
        from meerk40t.core.units import Length
        import math
        if distance_limit is None:
            a=self.service.view.iposition(self._last_x,self._last_y)
            b=self.service.view.iposition(x,y)
            distance=math.hypot(b[0]-a[0],b[1]-a[1])
            threshold=float(Length(self.service.delay_distance_long))
            delay=self.service.delay_jump_long if distance>threshold else self.service.delay_jump_short
            return super().list_jump(round(x),round(y),short=round(delay/10))
        return super().list_jump(round(x),round(y),
            short=round((self.service.delay_jump_short if short is None else short)/10),
            long=round((self.service.delay_jump_long if long is None else long)/10),distance_limit=distance_limit)

    def list_mark(self,x,y,angle=0):
        return super().list_mark(round(x),round(y),angle)
