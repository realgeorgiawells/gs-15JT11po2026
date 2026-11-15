"""Draws the Goalscraper logo (a sword driven through a football) as SVG, then PNG app icons via rsvg-convert."""
import math
import subprocess
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"


def pentagon(cx, cy, r, rot=-90):
    return [(cx + r * math.cos(math.radians(rot + i * 72)), cy + r * math.sin(math.radians(rot + i * 72))) for i in range(5)]


def path(pts, close=True):
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    return d + (" Z" if close else "")


def ball(r):
    """Classic panel pattern: a central pentagon, five seams out to five edge pentagons (clipped by the ball)."""
    inner = pentagon(0, 0, r * 0.36)
    parts = [f'<path d="{path(inner)}" class="pent"/>']
    for i, (x, y) in enumerate(inner):
        ang = math.atan2(y, x)
        ex, ey = r * 0.66 * math.cos(ang), r * 0.66 * math.sin(ang)
        parts.append(f'<path d="M{x:.1f},{y:.1f} L{ex:.1f},{ey:.1f}" class="seam"/>')
        # edge pentagon pointing inward, centred near the rim
        ox, oy = r * 0.98 * math.cos(ang), r * 0.98 * math.sin(ang)
        pts = pentagon(ox, oy, r * 0.33, rot=math.degrees(ang) + 180)
        parts.append(f'<path d="{path(pts)}" class="pent"/>')
        # seams between neighbouring edge pentagons
        a2 = ang + math.radians(36)
        sx, sy = r * 0.66 * math.cos(ang), r * 0.66 * math.sin(ang)
        tx, ty = r * 0.9 * math.cos(a2), r * 0.9 * math.sin(a2)
        parts.append(f'<path d="M{sx:.1f},{sy:.1f} L{tx:.1f},{ty:.1f}" class="seam"/>')
        tx2, ty2 = r * 0.9 * math.cos(ang - math.radians(36)), r * 0.9 * math.sin(ang - math.radians(36))
        parts.append(f'<path d="M{sx:.1f},{sy:.1f} L{tx2:.1f},{ty2:.1f}" class="seam"/>')
    return "\n      ".join(parts)


def svg(background=True, scale=1.0, size=512):
    R = 118
    bg = ""
    if background:
        bg = """<rect x="0" y="0" width="512" height="512" rx="112" fill="url(#plate)"/>
  <rect x="14" y="14" width="484" height="484" rx="100" fill="none" stroke="url(#gold)" stroke-width="5" opacity=".85"/>
  <rect x="24" y="24" width="464" height="464" rx="92" fill="none" stroke="#000" stroke-opacity=".35" stroke-width="2"/>"""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="{size}" height="{size}">
  <defs>
    <linearGradient id="plate" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#3a4048"/><stop offset=".5" stop-color="#1f2328"/><stop offset="1" stop-color="#121417"/>
    </linearGradient>
    <linearGradient id="gold" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#f1d98e"/><stop offset=".45" stop-color="#c9a54a"/><stop offset="1" stop-color="#7d5f22"/>
    </linearGradient>
    <linearGradient id="blade" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#8d949c"/><stop offset=".48" stop-color="#f4f6f8"/><stop offset=".52" stop-color="#b9c0c7"/><stop offset="1" stop-color="#5d646b"/>
    </linearGradient>
    <radialGradient id="ball" cx=".38" cy=".32" r=".8">
      <stop offset="0" stop-color="#f2f4f6"/><stop offset=".55" stop-color="#b8bec5"/><stop offset="1" stop-color="#5a6168"/>
    </radialGradient>
    <clipPath id="ballclip"><circle cx="0" cy="0" r="{R}"/></clipPath>
    <style>
      .pent{{fill:#23272d;stroke:#16191d;stroke-width:3;stroke-linejoin:round}}
      .seam{{stroke:#2d3238;stroke-width:3.5;stroke-linecap:round}}
    </style>
  </defs>
  {bg}
  <g transform="translate(256 262) scale({scale})">
    <g transform="rotate(-32)">
      <!-- blade (behind the ball, so it enters at the top and leaves at the bottom) -->
      <path d="M-19,-122 L19,-122 L15,190 L0,228 L-15,190 Z" fill="url(#blade)" stroke="#2a2e33" stroke-width="3" stroke-linejoin="round"/>
      <path d="M0,-118 L0,186" stroke="#6b7279" stroke-width="3" opacity=".8"/>
    </g>
    <circle cx="0" cy="0" r="{R + 6}" fill="#0d0f12" opacity=".35"/>
    <circle cx="0" cy="0" r="{R}" fill="url(#ball)"/>
    <g clip-path="url(#ballclip)">
      {ball(R)}
    </g>
    <circle cx="0" cy="0" r="{R}" fill="none" stroke="url(#gold)" stroke-width="5"/>
    <g transform="rotate(-32)">
      <!-- the cut where the blade enters and leaves -->
      <path d="M-21,-{R - 2} L21,-{R - 2}" stroke="#0d0f12" stroke-width="7" stroke-linecap="round"/>
      <path d="M-17,{R - 4} L17,{R - 4}" stroke="#0d0f12" stroke-width="6" stroke-linecap="round" opacity=".7"/>
      <!-- crossguard, grip and pommel -->
      <path d="M-74,-140 Q-80,-129 -72,-122 L72,-122 Q80,-129 74,-140 Q0,-128 -74,-140 Z" fill="url(#gold)" stroke="#5c4415" stroke-width="3" stroke-linejoin="round"/>
      <rect x="-12" y="-198" width="24" height="60" rx="5" fill="#3b2a18" stroke="#1d140a" stroke-width="2.5"/>
      <path d="M-12,-186 L12,-178 M-12,-172 L12,-164 M-12,-158 L12,-150" stroke="#c9a54a" stroke-width="3"/>
      <circle cx="0" cy="-212" r="17" fill="url(#gold)" stroke="#5c4415" stroke-width="3"/>
      <circle cx="0" cy="-212" r="6" fill="#7d5f22"/>
    </g>
  </g>
</svg>
"""


if __name__ == "__main__":
    (WEB / "icons").mkdir(parents=True, exist_ok=True)
    (WEB / "logo.svg").write_text(svg(background=False))
    (WEB / "icons" / "icon.svg").write_text(svg(background=True))
    (WEB / "icons" / "maskable.svg").write_text(svg(background=True, scale=0.8))
    for name, src, size in [("icon-180.png", "icon.svg", 180), ("icon-192.png", "icon.svg", 192),
                            ("icon-512.png", "icon.svg", 512), ("maskable-512.png", "maskable.svg", 512),
                            ("favicon-32.png", "icon.svg", 32)]:
        subprocess.run(["rsvg-convert", "-w", str(size), "-h", str(size), str(WEB / "icons" / src),
                        "-o", str(WEB / "icons" / name)], check=True)
    print("logo and icons written")
