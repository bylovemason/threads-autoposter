"""
Quote-card generator for Love Mason's LinkedIn image posts.

Black 1000x1250 card in tweet style: circular avatar, "Love Mason" with a
blue verified badge, "Career-to-Business Coach", then a few short punchy
white text blocks.

Usage:
  python linkedin/make_card.py out.png "Block one" "Block two" "Block three" "Block four"
  python linkedin/make_card.py --batch linkedin/queue.json     # renders every queue item with "card_blocks"

Needs Pillow (pip install pillow). Renders locally / by Claude when writing a
batch; the GitHub poster only uploads the finished PNG.
"""

import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "assets", "fonts")
W, H = 1000, 1250
MARGIN = 84
BG = (0, 0, 0)
WHITE = (255, 255, 255)
GREY = (139, 152, 165)
BLUE = (29, 155, 240)


def font(weight, size):
    return ImageFont.truetype(os.path.join(FONTS, f"Inter-{weight}.otf"), size)


def wrap(draw, text, fnt, width):
    lines = []
    for para in text.split("\n"):
        words, line = para.split(), ""
        for w in words:
            trial = f"{line} {w}".strip()
            if draw.textlength(trial, font=fnt) <= width:
                line = trial
            else:
                if line:
                    lines.append(line)
                line = w
        lines.append(line)
    return lines


def avatar_image(path, size):
    if path and os.path.exists(path):
        img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        img = ImageOps.fit(img, (size, size), centering=(0.5, 0.4))
    else:
        img = Image.new("RGB", (size, size), (60, 60, 60))
        d = ImageDraw.Draw(img)
        f = font("Bold", size // 3)
        d.text((size / 2, size / 2), "LM", font=f, fill=WHITE, anchor="mm")
    mask = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * 4, size * 4), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask.resize((size, size), Image.LANCZOS))
    return out


def badge(size):
    s = size * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c, pts, n = s / 2, [], 16
    for i in range(n * 2):
        r = s / 2 if i % 2 == 0 else s / 2 * 0.84
        a = math.pi * i / n - math.pi / 2
        pts.append((c + r * math.cos(a), c + r * math.sin(a)))
    d.polygon(pts, fill=BLUE)
    d.line([(s * 0.29, s * 0.52), (s * 0.44, s * 0.66), (s * 0.72, s * 0.36)],
           fill=WHITE, width=int(s * 0.1), joint="curve")
    return img.resize((size, size), Image.LANCZOS)


def render(blocks, out_path, name="Love Mason", subtitle="Career-to-Business Coach", avatar=None):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    text_w = W - 2 * MARGIN
    av = 132
    head_h = av

    # Biggest text size that fits the card.
    for size in range(58, 30, -2):
        f = font("SemiBold", size)
        gap = int(size * 1.15)
        line_h = int(size * 1.32)
        wrapped = [wrap(d, b, f, text_w) for b in blocks]
        body_h = sum(len(l) * line_h for l in wrapped) + gap * (len(blocks) - 1)
        total = head_h + 70 + body_h
        if total <= H - 2 * MARGIN:
            break

    y = (H - total) // 2
    img.paste(avatar_image(avatar, av), (MARGIN, y), avatar_image(avatar, av))
    nx = MARGIN + av + 28
    fn = font("Bold", 44)
    fs = font("Regular", 34)
    d.text((nx, y + av / 2 - 6), name, font=fn, fill=WHITE, anchor="ls")
    bx = nx + d.textlength(name, font=fn) + 12
    b = badge(40)
    img.paste(b, (int(bx), int(y + av / 2 - 41)), b)
    d.text((nx, y + av / 2 + 14), subtitle, font=fs, fill=GREY, anchor="lt")

    y += head_h + 70
    for lines in wrapped:
        for line in lines:
            d.text((MARGIN, y), line, font=f, fill=WHITE)
            y += line_h
        y += gap
    img.save(out_path, "PNG", optimize=True)
    return out_path


def card_settings():
    with open(os.path.join(HERE, "config.json"), encoding="utf-8") as fh:
        c = json.load(fh).get("card", {})
    av = c.get("avatar")
    return dict(name=c.get("name", "Love Mason"),
                subtitle=c.get("subtitle", "Career-to-Business Coach"),
                avatar=os.path.join(HERE, av) if av else None)


def main():
    args = sys.argv[1:]
    s = card_settings()
    if args[:1] == ["--batch"]:
        path = args[1]
        with open(path, encoding="utf-8") as fh:
            queue = json.load(fh)
        for item in queue:
            if item.get("card_blocks"):
                stamp = item["at"].replace(" ", "_").replace(":", "")
                item.setdefault("image", f"cards/{stamp}.png")
                render(item["card_blocks"], os.path.join(HERE, item["image"]), **s)
                print("rendered", item["image"])
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(queue, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        return
    if len(args) < 2:
        sys.exit(__doc__)
    render(args[1:], args[0], **s)
    print("rendered", args[0])


if __name__ == "__main__":
    main()
