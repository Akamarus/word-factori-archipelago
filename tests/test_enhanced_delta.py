import base64
import unittest
from tools import enhanced_delta


class DeltaTests(unittest.TestCase):
    def test_insert_delete_replace_roundtrip_uses_copy_ranges(self):
        original = bytes(range(256)) * 200
        patched = b"authored header" + original[:12345] + b"authored edit" + original[13000:] + b"tail"
        delta = enhanced_delta.build_delta(original, patched)
        self.assertEqual(patched, enhanced_delta.apply_delta(original, delta))
        self.assertTrue(any(op[0] == "copy" for op in delta["operations"]))
        self.assertLess(sum(len(base64.b64decode(op[1])) for op in delta["operations"] if op[0] == "data"), len(original) // 3)

    def test_wrong_base_and_invalid_ranges_fail_closed(self):
        delta = enhanced_delta.build_delta(b"base", b"result")
        with self.assertRaises(ValueError): enhanced_delta.apply_delta(b"other", delta)
        for operations in ([['copy', -1, 10]], [['copy', 0, 999999]], [['data', '!!!']], [['unknown']]):
            with self.assertRaises(ValueError): enhanced_delta.apply_delta(b"base", {**delta, "operations": operations})

    def test_corrupted_output_rejected(self):
        delta = enhanced_delta.build_delta(b"base", b"result")
        delta["operations"] = [["data", base64.b64encode(b"wrong!").decode()]]
        with self.assertRaises(ValueError): enhanced_delta.apply_delta(b"base", delta)


if __name__ == "__main__": unittest.main()
