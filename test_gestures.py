import importlib.util
import pathlib
import unittest

spec=importlib.util.spec_from_file_location('motion_wheel',pathlib.Path(__file__).with_name('motion-wheel.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class Gestures(unittest.TestCase):
    def test_thumb_arcs_and_rejections(self):
        cases=[
            ('long_up',[(100,200,0),(100,160,.1),(100,100,.2)],5),
            ('long_down',[(100,100,0),(100,140,.1),(100,200,.2)],4),
            ('right_arc_up',[(100,200,0),(103,191,.07),(110,184,.14),(120,180,.21)],5),
            ('left_arc_up',[(100,200,0),(97,191,.07),(90,184,.14),(80,180,.21)],5),
            ('right_arc_down',[(100,100,0),(103,109,.07),(110,116,.14),(120,120,.21)],4),
            ('left_arc_down',[(100,100,0),(97,109,.07),(90,116,.14),(80,120,.21)],4),
            ('short_up',[(100,130,0),(101,117,.08),(100,103,.16)],5),
            ('short_diagonal',[(100,130,0),(110,120,.08),(121,109,.16)],5),
            ('small_tail_recoil',[(100,130,0),(108,110,.08),(120,100,.16),(121,104,.24)],5),
            ('tap',[(100,100,0)],None),
            ('two_positions',[(100,200,0),(100,100,.2)],None),
            ('horizontal',[(10,100,0),(50,102,.1),(100,100,.2)],None),
            ('mostly_horizontal',[(100,100,0),(125,109,.1),(160,120,.2)],None),
            ('jitter',[(100,100,0),(102,102,.1),(100,100,.2)],None),
            ('short_jitter',[(100,100,0),(108,109,.1),(110,112,.2)],None),
            ('reverse',[(100,100,0),(100,200,.1),(100,120,.2)],None),
            ('fast_jump',[(100,100,0),(120,120,.005),(140,140,.01)],None),
            ('large_jump',[(100,400,0),(100,200,.1),(100,100,.2)],None),
            ('horizontal_loop',[(100,100,0),(150,105,.1),(100,110,.2),(50,115,.3),(100,130,.4)],None),
        ]
        for name,points,expected in cases:
            with self.subTest(name=name):self.assertEqual(module.classify(points),expected)

if __name__=='__main__':unittest.main()
