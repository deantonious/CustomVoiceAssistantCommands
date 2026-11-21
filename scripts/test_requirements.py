"""Print the requirements of the Home Assistant components Assist Utils tests load.

pytest-homeassistant-custom-component installs Home Assistant core but not the
requirements of individual components. Usage:

    python scripts/test_requirements.py > /tmp/reqs.txt && uv pip install -r /tmp/reqs.txt
"""

import json
from pathlib import Path

import homeassistant.components as components

COMPONENTS = ["assist_pipeline", "assist_satellite", "conversation", "ffmpeg", "stt", "tts", "wake_word"]

base = Path(components.__file__).parent
requirements: set[str] = set()
for name in COMPONENTS:
    manifest = base / name / "manifest.json"
    if manifest.is_file():
        requirements |= set(json.loads(manifest.read_text()).get("requirements", []))
print("\n".join(sorted(requirements)))
