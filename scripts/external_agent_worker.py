#!/usr/bin/env python3
"""JSON-lines bridge to an explicitly installed third-party agent bundle.

A separate process prevents Python module/state collisions. It is not a security
sandbox; only run reviewed agent code and trusted checkpoints.
"""
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import traceback

bundle = Path(sys.argv[1]).resolve()
engine = Path(sys.argv[2]).resolve()
sys.path[:0] = [str(bundle), str(engine)]
os.chdir(bundle)
try:
    with contextlib.redirect_stdout(sys.stderr):
        spec = importlib.util.spec_from_file_location('benchmark_agent', bundle / 'main.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    print(json.dumps({'ready': True}), flush=True)
    for line in sys.stdin:
        try:
            with contextlib.redirect_stdout(sys.stderr):
                action = module.agent(json.loads(line))
            print(json.dumps({'action': action, 'policy_evals': getattr(getattr(module, 'SA', None), 'evals', None)}), flush=True)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            print(json.dumps({'error': 'external agent raised an exception'}), flush=True)
except Exception:
    traceback.print_exc(file=sys.stderr)
    print(json.dumps({'error': 'external agent initialization failed'}), flush=True)
    sys.exit(1)
