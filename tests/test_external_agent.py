import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from ptcg.external import ExternalAgent


class ExternalAgentTest(unittest.TestCase):
    def test_worker_uses_own_bundle_and_does_not_inherit_api_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            (bundle / 'deck.csv').write_text('1\n' * 60)
            (bundle / 'main.py').write_text('''import os
counter = 0
def agent(obs):
    global counter
    if os.getenv("KAGGLE_API_TOKEN"):
        raise RuntimeError("credential leaked")
    if obs.get("select") is None:
        return [1] * 60
    counter += 1
    return [counter - 1]
''')
            with patch.dict(os.environ, {'KAGGLE_API_TOKEN': 'test-sentinel'}):
                with ExternalAgent(bundle, timeout=10) as agent:
                    self.assertEqual(agent.act({'select': {}}), [0])
                    self.assertEqual(agent.act({'select': {}}), [1])


if __name__ == '__main__':
    unittest.main()
