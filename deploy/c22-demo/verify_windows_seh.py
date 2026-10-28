"""Manual Windows/Wine exception control; no MT5, credentials or order APIs.

Run with the dedicated Windows Python before attempting terminal compatibility.
An arbitrary OSError is insufficient: the read/write fault and address must match.
"""

import ctypes
import sys
import unittest


@unittest.skipUnless(sys.platform == "win32", "Requires Windows Python or Wine")
class WindowsExceptionTests(unittest.TestCase):
    def setUp(self):
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.module = self.kernel.GetModuleHandleA
        self.module.argtypes = [ctypes.c_void_p]
        self.module.restype = ctypes.c_void_p

    def assert_access_violation(self, operation, callback):
        self.assertTrue(self.module(None), "Valid DLL call failed before fault")
        with self.assertRaises(OSError) as caught:
            callback()
        message = str(caught.exception).lower()
        self.assertIn("access violation " + operation, message)
        self.assertIn("0x0000000000000020", message)
        self.assertTrue(self.module(None), "Valid DLL call failed after fault")

    def test_access_violation_read_and_recovery(self):
        self.assert_access_violation("reading", lambda: self.module(0x20))

    def test_access_violation_write_and_recovery(self):
        copy = self.kernel.RtlMoveMemory
        copy.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
        copy.restype = None
        source = ctypes.create_string_buffer(b"X")
        self.assert_access_violation("writing", lambda: copy(0x20, ctypes.addressof(source), 1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
