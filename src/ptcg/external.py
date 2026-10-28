"""Run a pinned third-party agent in a separate Python process, not a sandbox."""
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import tempfile

from .battle import ROOT, SAMPLE


class ExternalAgent:
    def __init__(self, bundle, timeout=120):
        self.bundle = Path(bundle).resolve()
        self.timeout = timeout
        self.policy_evals = None
        self._stderr_pos = 0
        self._stderr = tempfile.TemporaryFile(mode='w+t')
        self.proc = subprocess.Popen(
            [sys.executable, '-I', '-u', str(ROOT / 'scripts/external_agent_worker.py'), str(self.bundle), str(SAMPLE)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._stderr,
            text=True, bufsize=1, env={'PATH': os.defpath, 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', 'PTCG_DEBUG': '1', 'TORCH_FORCE_WEIGHTS_ONLY_LOAD': '1'})
        try:
            result = self._read()
            if not result.get('ready'):
                raise RuntimeError('External agent failed to initialize')
            deck = self.act({'select': None, 'current': None, 'logs': []})
            expected = [int(x) for x in (self.bundle / 'deck.csv').read_text().splitlines() if x.strip()]
            if sorted(deck) != sorted(expected):
                raise ValueError('External agent returned a different deck than deck.csv')
        except BaseException:
            self.close()
            raise

    def _read(self):
        selector = selectors.DefaultSelector()
        try:
            selector.register(self.proc.stdout, selectors.EVENT_READ)
            if not selector.select(self.timeout):
                raise TimeoutError('External agent timed out')
            line = self.proc.stdout.readline()
        finally:
            selector.close()
        if not line:
            self._stderr.flush()
            self._stderr.seek(0)
            raise RuntimeError('External agent exited: ' + self._stderr.read()[-4000:])
        response = json.loads(line)
        if 'error' in response:
            self._stderr.flush()
            self._stderr.seek(0)
            raise RuntimeError(response['error'] + ': ' + self._stderr.read()[-4000:])
        return response

    def act(self, obs):
        self.proc.stdin.write(json.dumps(obs, separators=(',', ':')) + '\n')
        self.proc.stdin.flush()
        response = self._read()
        self.policy_evals = response.get('policy_evals')
        self._stderr.flush()
        self._stderr.seek(self._stderr_pos)
        diagnostics = self._stderr.read()
        self._stderr_pos = self._stderr.tell()
        if 'Traceback (most recent call last)' in diagnostics:
            raise RuntimeError('External agent fell back after exception: ' + diagnostics[-4000:])
        return response['action']

    def close(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        for stream in (self.proc.stdin, self.proc.stdout, self._stderr):
            if stream:
                stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
