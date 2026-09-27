from __future__ import annotations
import sys
import os

# Ensure stage-4 directory is in Python path for Vercel Serverless environment
curr_dir = os.path.dirname(os.path.abspath(__file__))
stage4_dir = os.path.join(curr_dir, "..", "stage-4")
if stage4_dir not in sys.path:
    sys.path.insert(0, stage4_dir)

from app.main import app

# Vercel ASGI Handler
app = app
