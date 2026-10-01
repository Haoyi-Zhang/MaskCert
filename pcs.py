#!/usr/bin/env python3
"""Offline finite-plan certificate interface. No address or packet operations."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
from pcs.cli import main
if __name__ == '__main__':
    raise SystemExit(main())
