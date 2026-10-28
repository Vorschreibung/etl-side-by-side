#!/usr/bin/env python3
"""Build a standalone HTML page comparing timestamped screenshot pairs."""

import argparse
import base64
import html
from pathlib import Path
import re
import sys


IMAGE_NAME = re.compile(r"(?P<name>.+)_shot_(?P<timestamp>\d+)\.png", re.IGNORECASE)


def find_pairs(directory):
    """Group related screenshots and pair consecutive timestamps within each group."""
    groups = {}
    for path in sorted(directory.iterdir()):
        match = IMAGE_NAME.fullmatch(path.name)
        if path.is_file() and match:
            groups.setdefault(match['name'], []).append(
                (int(match['timestamp']), path)
            )

    if not groups:
        raise ValueError(f"No images matching <name>_shot_<timestamp>.png in {directory}")

    pairs = []
    for name, images in sorted(groups.items()):
        images.sort()
        if len(images) % 2:
            raise ValueError(f"Unpaired image in group {name!r}: found {len(images)} images")
        for index in range(0, len(images), 2):
            pairs.append((name, images[index][1], images[index + 1][1]))
    return pairs


def image_uri(path):
    """Embed image bytes so the resulting HTML has no external dependencies."""
    encoded = base64.b64encode(path.read_bytes()).decode('ascii')
    return f"data:image/png;base64,{encoded}"


def render_pair(index, name, first, second):
    title = html.escape(name)
    first_name = html.escape(first.name, quote=True)
    second_name = html.escape(second.name, quote=True)
    return f'''<section class="comparison" aria-label="{index + 1}. {title}">
  <div class="stage" style="--split: 50%">
    <div class="image-layer second">
      <img src="{image_uri(second)}" alt="{second_name}" draggable="false">
      <span class="renderer vulkan">VULKAN</span>
    </div>
    <div class="image-layer first">
      <img src="{image_uri(first)}" alt="{first_name}" draggable="false">
      <span class="renderer opengl">OPENGL</span>
    </div>
    <div class="divider" aria-hidden="true"><span>&lsaquo;&nbsp;&rsaquo;</span></div>
    <input class="slider" type="range" min="0" max="100" step="0.1" value="50"
      aria-label="Image split for {title}. Left is the first image; right is the second."
      aria-valuetext="50% first image, 50% second image">
  </div>
</section>'''


PAGE_START = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Screenshot comparisons</title>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; background: #11151c; color: #eef2f7;
         font: 14px/1.5 system-ui, sans-serif; }
  .comparison { height: 100vh; height: 100svh; display: flex;
                flex-direction: column; border-bottom: 1px solid #435066; }
  .stage { position: relative; flex: 1; min-height: 0; overflow: hidden;
           background: #080b10; }
  /* Both images retain the full stage dimensions; clipping never resizes either. */
  .image-layer { position: absolute; inset: 0; pointer-events: none; }
  .stage img { position: absolute; inset: 0; width: 100%; height: 100%;
               object-fit: contain; user-select: none; pointer-events: none; }
  .first { clip-path: inset(0 calc(100% - var(--split)) 0 0); }
  .second { clip-path: inset(0 0 0 var(--split)); }
  /* Labels belong to their clipped image and stay inside its letterboxed bounds. */
  .renderer { position: absolute; top: calc(var(--image-top, 0px) + 16px);
              font-size: clamp(18px, 3vw, 32px); font-weight: 800;
              text-shadow: 1px 1px 2px #000, 0 0 6px #000, 0 0 12px #000; }
  .opengl { left: calc(var(--image-left, 0px) + 16px); color: #00ff00; }
  .vulkan { right: calc(var(--image-left, 0px) + 16px); color: #ff0000; }
  .divider { position: absolute; top: 0; bottom: 0; left: var(--split);
             width: 2px; background: white; transform: translateX(-50%);
             box-shadow: 0 0 4px #000; pointer-events: none; }
  .divider span { position: absolute; top: 50%; left: 50%;
                  transform: translate(-50%, -50%); width: 44px; height: 44px;
                  border: 2px solid white; border-radius: 50%; background: #182334;
                  display: grid; place-items: center; font-size: 24px; }
  /* The native range supplies focus and keyboard behavior; pointer math below
     makes the split reach both exact edges regardless of thumb dimensions. */
  .slider { position: absolute; inset: 0; width: 100%; height: 100%; margin: 0;
            opacity: 0; cursor: ew-resize; touch-action: pan-y; }
  .stage:focus-within { outline: 3px solid #70b7ff; outline-offset: -3px; }
</style>
</head>
<body>
<main aria-label="Screenshot comparisons. Drag to compare, or focus a slider and use arrow keys.">
'''

PAGE_END = '''
</main>
<script>
  document.querySelectorAll('.slider').forEach(slider => {
    const stage = slider.parentElement;
    let activePointer = null;

    // Match each label's inset to the image area produced by object-fit: contain.
    stage.querySelectorAll('.image-layer').forEach(layer => {
      const image = layer.querySelector('img');
      function positionLabel() {
        if (!image.naturalWidth || !image.naturalHeight) return;
        const scale = Math.min(stage.clientWidth / image.naturalWidth,
          stage.clientHeight / image.naturalHeight);
        layer.style.setProperty('--image-left',
          `${(stage.clientWidth - image.naturalWidth * scale) / 2}px`);
        layer.style.setProperty('--image-top',
          `${(stage.clientHeight - image.naturalHeight * scale) / 2}px`);
      }
      image.addEventListener('load', positionLabel);
      new ResizeObserver(positionLabel).observe(stage);
      positionLabel();
    });

    function update() {
      const value = Number(slider.value);
      stage.style.setProperty('--split', `${value}%`);
      slider.setAttribute('aria-valuetext',
        `${value}% first image, ${Number((100 - value).toFixed(1))}% second image`);
    }

    function move(event) {
      const bounds = stage.getBoundingClientRect();
      slider.value = Math.max(0, Math.min(100,
        (event.clientX - bounds.left) / bounds.width * 100));
      update();
    }

    slider.addEventListener('input', update);
    slider.addEventListener('pointerdown', event => {
      if (event.button !== 0 || activePointer !== null) return;
      event.preventDefault();
      activePointer = event.pointerId;
      slider.focus({ preventScroll: true });
      slider.setPointerCapture(event.pointerId);
      move(event);
    });
    slider.addEventListener('pointermove', event => {
      if (event.pointerId === activePointer) move(event);
    });
    slider.addEventListener('pointerup', event => {
      if (event.pointerId !== activePointer) return;
      move(event);
      slider.releasePointerCapture(event.pointerId);
      activePointer = null;
    });
    slider.addEventListener('lostpointercapture', () => { activePointer = null; });
  });
</script>
</body>
</html>
'''


def main():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', nargs='?', type=Path, default=root / 'side-by-side',
                        help='Screenshot directory (default: side-by-side beside this script)')
    parser.add_argument('-o', '--output', type=Path, default=root / 'comparisons.html',
                        help='Output HTML path (default: comparisons.html beside this script)')
    args = parser.parse_args()

    try:
        pairs = find_pairs(args.directory)
        # Stream each section to avoid holding the entire embedded page in memory.
        with args.output.open('w', encoding='utf-8') as output:
            output.write(PAGE_START)
            for index, (name, first, second) in enumerate(pairs):
                output.write(render_pair(index, name, first, second))
            output.write(PAGE_END)
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"Created {args.output.resolve()} with {len(pairs)} comparison(s).")
    return 0


if __name__ == '__main__':
    sys.exit(main())
