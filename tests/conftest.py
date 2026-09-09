"""让从任意目录调用 pytest 都使用本项目的 harness。"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
