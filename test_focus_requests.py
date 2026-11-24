"""Keep the tap IPC from acting on stale requests or unrelated windows."""
import json
import pathlib
import sys
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from focus_repair import parse_tap

class FocusRequestTest(unittest.TestCase):
    def test_only_recent_mapped_window(self):
        mapped={4242:9001}
        self.assertEqual(parse_tap(b'{"window":4242,"tapAt":99.9}',100,mapped),(4242,99.9))
        rejected=[
            {'window':1,'tapAt':99.9},
            {'window':4242,'tapAt':98},
            {'window':4242,'tapAt':101},
            {'window':True,'tapAt':99.9},
            {'window':'4242','tapAt':99.9},
            {'window':4242,'tapAt':True},
            {'window':4242,'tapAt':float('nan')},
            {'window':4242,'tapAt':float('inf')},
            {'window':4242,'tapAt':10**400},
            {'window':4242,'tapAt':99.9,'command':'other'},
        ]
        for value in rejected:
            with self.subTest(value=value):self.assertIsNone(parse_tap(json.dumps(value).encode(),100,mapped))
        for raw in (b'invalid',b'null',b'[]',b'{}'):
            with self.subTest(raw=raw):self.assertIsNone(parse_tap(raw,100,mapped))

if __name__=='__main__':unittest.main()
