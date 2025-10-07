#!/usr/bin/env python3
"""Launcher script for NESendo GUI."""
import sys
import os

# Add the NESendo package to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'NESendo'))

from NESendo.app.gui import main

if __name__ == "__main__":
    main()
