from __future__ import annotations

import io
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

from scripts.build import NAME, make_run, make_zip


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dbzk-package-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.files = {'install.py': b'import sys\nprint("TEST BOOTSTRAP " + str(sys.argv[1:]))\n',
                      'payload/test file.dll': b'NON-EXECUTABLE TEST DATA'}

    def write_run(self, data=None):
        path = self.base / 'Installer with spaces.run'
        path.write_bytes(make_run(self.files) if data is None else data)
        return path

    def test_builds_are_repeatable(self):
        self.assertEqual(make_run(self.files), make_run(self.files))
        self.assertEqual(make_zip(self.files), make_zip(self.files))

    def test_zip_positive_list_and_executable_mode(self):
        with zipfile.ZipFile(io.BytesIO(make_zip(self.files))) as archive:
            self.assertEqual(set(archive.namelist()), {NAME + '/' + name for name in self.files})
            self.assertEqual(archive.read(NAME + '/payload/test file.dll'), b'NON-EXECUTABLE TEST DATA')
            self.assertEqual((archive.getinfo(NAME + '/install.py').external_attr >> 16) & 0o777, 0o755)

    def test_self_extractor_and_existing_directory_refusal(self):
        path = self.write_run()
        destination = self.base / 'extracted with spaces'
        result = subprocess.run(['bash', str(path), '--extract', str(destination)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((destination / 'payload/test file.dll').read_bytes(), self.files['payload/test file.dll'])
        again = subprocess.run(['bash', str(path), '--extract', str(destination)], capture_output=True)
        self.assertNotEqual(again.returncode, 0)

    def test_self_extractor_checksum_and_traversal_refusal(self):
        data = bytearray(make_run(self.files))
        data[-8] ^= 1
        result = subprocess.run(['bash', str(self.write_run(data)), '--extract', str(self.base / 'damaged')], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.base / 'damaged').exists())
        malicious = make_run({'../escape': b'not extracted'})
        result = subprocess.run(['bash', str(self.write_run(malicious)), '--extract', str(self.base / 'unsafe')], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.base / 'escape').exists())

    def test_bootstrap_forwards_arguments_without_shell_evaluation(self):
        path = self.write_run()
        marker = self.base / 'must-not-exist'
        value = '$(touch ' + str(marker) + ')'
        result = subprocess.run(['bash', str(path), '--check', value], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--check', result.stdout)
        self.assertIn('$(touch ', result.stdout)
        self.assertFalse(marker.exists())


if __name__ == '__main__':
    unittest.main()
