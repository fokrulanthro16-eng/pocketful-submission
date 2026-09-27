import os, glob, subprocess, time
import imageio_ffmpeg
from playwright.sync_api import sync_playwright

ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
raw_dir = os.path.abspath("assets/raw_record")
os.makedirs(raw_dir, exist_ok=True)
for f in glob.glob(os.path.join(raw_dir, "*")):
    try: os.remove(f)
    except Exception: pass

output_mp4 = os.path.abspath("assets/walkthrough_demo.mp4")
if os.path.exists(output_mp4):
    try: os.remove(output_mp4)
    except Exception: pass

print("[1/4] Launching Chromium browser with full 1080p viewport...", flush=True)
with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-setuid-sandbox"]
    )
    context = browser.new_context(
        record_video_dir=raw_dir,
        record_video_size={"width": 1920, "height": 1080},
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    page = context.new_page()
    
    print("[2/4] Navigating to live Pocketful app...", flush=True)
    page.goto("https://pocketful-fintech.vercel.app", wait_until="networkidle", timeout=60000)
    time.sleep(6)  # Crucial: wait for Next.js hydration and charts to render

    # Scripted interactions covering all dashboard components (~75 seconds)
    sections = [
        ("Overview & Metrics", 0, 10),
        ("Liquidity & Treasury Charts", 600, 12),
        ("Account Balances & Reconciliation", 1300, 12),
        ("Audit Logs & System Activity", 2100, 14),
        ("Deep Table Inspection", 2800, 10),
        ("Reconciliation Status View", 1500, 8),
        ("Back to Top Dashboard", 0, 9)
    ]

    for label, scroll_y, duration in sections:
        print(f"  -> Recording {label} (scroll: {scroll_y}px)", flush=True)
        page.evaluate(f"window.scrollTo({{top: {scroll_y}, behavior: 'smooth'}})")
        time.sleep(duration)

    context.close()
    browser.close()

print("[3/4] Processing raw video and syncing voiceover...", flush=True)
time.sleep(2)
raw_vids = glob.glob(os.path.join(raw_dir, "*.webm"))
if not raw_vids:
    raise RuntimeError("Recording failed: no webm file produced.")

voiceover = os.path.abspath("assets/voiceover.mp3")
cmd = [ffmpeg_exe, "-y", "-i", raw_vids[0]]

if os.path.exists(voiceover):
    cmd.extend([
        "-i", voiceover,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        output_mp4
    ])
else:
    cmd.extend([
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        output_mp4
    ])

subprocess.run(cmd, check=True)
size_mb = os.path.getsize(output_mp4) / (1024 * 1024)
print(f"[4/4] Video ready: {output_mp4} ({size_mb:.2f} MB)", flush=True)
