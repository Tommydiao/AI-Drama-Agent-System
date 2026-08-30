"""Phase-1 deterministic Mock media production using real FFmpeg artifacts."""
from __future__ import annotations

import subprocess
from pathlib import Path
from uuid import uuid4


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True, capture_output=True, text=True)


def render_three_shot_story(storage_root: Path, project_id: str, title: str, shot_count: int = 15, shot_seconds: int = 4) -> tuple[str, Path]:
    output_dir = storage_root / project_id
    output_dir.mkdir(parents=True, exist_ok=True)
    palette = ["0x172033", "0x3e2047", "0x193d35", "0x3d3119", "0x302144"]
    clips: list[Path] = []
    for number in range(1, shot_count + 1):
        color = palette[(number - 1) % len(palette)]
        clip = output_dir / f"shot-{number}.mp4"
        _run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=720x1280:r=30:d={shot_seconds}",
            "-f", "lavfi", "-i", f"sine=frequency={330 + number * 37}:sample_rate=48000:duration={shot_seconds}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-shortest", str(clip),
        ])
        clips.append(clip)
    subtitle = output_dir / "subtitles.srt"
    subtitle.write_text(
        f"1\n00:00:00,000 --> 00:00:04,000\n{title}：门外响起敲门声。\n\n"
        "2\n00:00:04,000 --> 00:00:08,000\n她屏住呼吸，望向门缝。\n\n"
        "3\n00:00:08,000 --> 00:00:12,000\n一个熟悉的声音说：我回来了。\n",
        encoding="utf-8",
    )
    manifest = output_dir / "clips.ffconcat"
    manifest.write_text("ffconcat version 1.0\n" + "".join(f"file '{clip.as_posix()}'\n" for clip in clips), encoding="utf-8")
    final_path = output_dir / "rough-cut.mp4"
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(manifest), "-c", "copy", str(final_path)])
    return str(uuid4()), final_path
