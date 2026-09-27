#!/usr/bin/env python3
"""Automated Video Walkthrough Recording & Audio Composition Script.

Records a live browser walkthrough at http://127.0.0.1:8080 using Playwright
and merges the resulting video with assets/voiceover.mp3 via ffmpeg into
assets/walkthrough_demo.mp4.
"""
from __future__ import annotations
import glob
import os
import shutil
import subprocess
import time
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8080"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")
TEMP_VIDEO_DIR = os.path.join(ASSETS_DIR, "temp_video")
VOICEOVER_PATH = os.path.join(ASSETS_DIR, "voiceover.mp3")
OUTPUT_MP4 = os.path.join(ASSETS_DIR, "walkthrough_demo.mp4")

# Set ffmpeg path
FFMPEG_EXE = "C:\\Users\\WALTON\\.gemini\\antigravity\\scratch\\bin\\ffmpeg.exe"
if not os.path.exists(FFMPEG_EXE):
    FFMPEG_EXE = "ffmpeg"

def record_browser_walkthrough():
    if os.path.exists(TEMP_VIDEO_DIR):
        shutil.rmtree(TEMP_VIDEO_DIR)
    os.makedirs(TEMP_VIDEO_DIR, exist_ok=True)

    print("[1/3] Starting Playwright browser recording...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            record_video_dir=TEMP_VIDEO_DIR,
            record_video_size={"width": 1280, "height": 720},
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()

        # Phase 1: Login
        print("  - Visiting login page...")
        page.goto(f"{BASE_URL}/login")
        page.wait_for_timeout(1000)
        page.fill("#login-email", "ada@example.com")
        page.wait_for_timeout(500)
        page.fill("#login-password", "correct horse")
        page.wait_for_timeout(500)
        page.click("button[data-testid='login-submit']")
        page.wait_for_timeout(1500)

        # Phase 2: Wallet Dashboard & Zero-Sum Inspection
        print("  - Exploring wallet dashboard and zero-sum invariant badge...")
        page.goto(f"{BASE_URL}/")
        page.wait_for_timeout(2000)
        
        # Smoothly scroll down through activity feed
        page.evaluate("window.scrollBy({ top: 350, behavior: 'smooth' })")
        page.wait_for_timeout(2500)

        # Send a payment in real-time
        print("  - Executing live payment transfer...")
        page.evaluate("window.scrollTo({ top: 150, behavior: 'smooth' })")
        page.wait_for_timeout(1000)
        page.fill("#pay-handle", "bob")
        page.wait_for_timeout(600)
        page.fill("#pay-amount", "50.00")
        page.wait_for_timeout(600)
        page.fill("#pay-note", "Autonomous Dark Factory Settlement")
        page.wait_for_timeout(600)
        page.click("button[data-testid='pay-submit']")
        page.wait_for_timeout(2000)

        # Scroll to view updated feed
        page.evaluate("window.scrollBy({ top: 400, behavior: 'smooth' })")
        page.wait_for_timeout(2500)

        # Phase 3: Enterprise Audit & Sentinel Tab
        print("  - Navigating to Enterprise Audit & Sentinel tab...")
        page.goto(f"{BASE_URL}/audit")
        page.wait_for_timeout(2500)

        # Scroll through SHA-256 blocks
        print("  - Inspecting SHA-256 chained blocks...")
        page.evaluate("window.scrollBy({ top: 350, behavior: 'smooth' })")
        page.wait_for_timeout(3000)

        # Scroll down to AML Sentinel
        print("  - Inspecting AML Sentinel security feed...")
        page.evaluate("window.scrollBy({ top: 400, behavior: 'smooth' })")
        page.wait_for_timeout(4000)

        # Scroll back up to summary cards
        page.evaluate("window.scrollTo({ top: 0, behavior: 'smooth' })")
        page.wait_for_timeout(3500)

        # Finish recording
        print("  - Finalizing recording...")
        page.close()
        context.close()
        browser.close()

    time.sleep(1)
    # Locate recorded video
    video_files = glob.glob(os.path.join(TEMP_VIDEO_DIR, "*.webm"))
    if not video_files:
        raise RuntimeError("No video file recorded by Playwright!")
    recorded_webm = video_files[0]
    print(f"[2/3] Raw browser video recorded: {recorded_webm} ({os.path.getsize(recorded_webm)} bytes)")
    return recorded_webm

def compose_with_audio(recorded_webm: str):
    print(f"[3/3] Merging video with neural voiceover via ffmpeg into {OUTPUT_MP4}...")
    
    cmd = [
        FFMPEG_EXE,
        "-y",
        "-i", recorded_webm,
        "-i", VOICEOVER_PATH,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        OUTPUT_MP4
    ]
    
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        print("FFmpeg stderr:\n", res.stderr)
        raise RuntimeError(f"FFmpeg composition failed with code {res.returncode}")

    # Clean up temp webm directory
    if os.path.exists(TEMP_VIDEO_DIR):
        shutil.rmtree(TEMP_VIDEO_DIR)

    file_size = os.path.getsize(OUTPUT_MP4)
    print(f"[SUCCESS] Final enterprise walkthrough demo generated: {OUTPUT_MP4} ({file_size} bytes)")

if __name__ == "__main__":
    webm = record_browser_walkthrough()
    compose_with_audio(webm)
