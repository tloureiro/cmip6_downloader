"""Run only the offline suite, from a disposable working directory."""
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
if sys.version_info < (3, 11):
    sys.exit('Checks require Python 3.11+; use a maintained Python release')
# Compile without creating bytecode; historical test/ scripts are never executed.
for path in [root / 'cmip6_downloader.py', root / 'test_downloader.py',
             root / 'tools/check_transfer.py', Path(__file__)]:
    compile(path.read_text(), str(path), 'exec')
runner = '''
import socket, subprocess, sys, unittest
from unittest.mock import patch
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
def denied(*args, **kwargs):
    raise AssertionError('Offline check forbids network/import side effects')
socket.socket.connect = denied
socket.create_connection = denied
with patch.object(subprocess, 'Popen', side_effect=denied), patch('builtins.open', side_effect=denied):
    import cmip6_downloader
suite = unittest.defaultTestLoader.discover(sys.argv[1], pattern='test_downloader.py')
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(not result.wasSuccessful())
'''
with tempfile.TemporaryDirectory(prefix='cmip6-check-') as work:
    result = subprocess.run([sys.executable, '-B', '-W', 'error', '-c', runner, str(root)],
                            cwd=work, timeout=60)
sys.exit(result.returncode)
