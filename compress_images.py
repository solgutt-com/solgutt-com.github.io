import os
from PIL import Image

THRESHOLD_BYTES = 1.5 * 1024 * 1024  # 1.5 MB
MAX_DIMENSION = 2400
QUALITY = 82
EXTENSIONS = ('.jpg', '.jpeg', '.png')
COLLECTIONS_ROOT = os.path.join(os.path.dirname(__file__), 'Images', 'Collections')

def compress_image(path):
    size = os.path.getsize(path)
    if size <= THRESHOLD_BYTES:
        print(f"  SKIP  {os.path.basename(path)} ({size / 1024 / 1024:.1f} MB)")
        return
    img = Image.open(path)
    w, h = img.size
    if max(w, h) > MAX_DIMENSION:
        scale = MAX_DIMENSION / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    img.save(path, "JPEG", quality=QUALITY, optimize=True)
    new_size = os.path.getsize(path)
    print(f"  OK    {os.path.basename(path)}  {size / 1024 / 1024:.1f} MB → {new_size / 1024 / 1024:.1f} MB")

def run():
    for root, dirs, files in os.walk(COLLECTIONS_ROOT):
        images = [f for f in files if f.lower().endswith(EXTENSIONS) and not f.startswith('.')]
        if not images:
            continue
        print(f"\n{os.path.relpath(root, COLLECTIONS_ROOT)}")
        for filename in sorted(images):
            compress_image(os.path.join(root, filename))

if __name__ == "__main__":
    run()
