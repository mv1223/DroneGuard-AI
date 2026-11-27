"""Generate synthetic sample security images and MP4 patrol video for testing & demos."""

from __future__ import annotations

from pathlib import Path
import cv2
import numpy as np

from config import SAMPLE_MEDIA_DIR


def _draw_scene_background(w: int = 640, h: int = 360, night: bool = False, label: str = "") -> np.ndarray:
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    if night:
        frame[:140, :] = (28, 22, 18)   # dark night sky
        frame[140:, :] = (38, 42, 40)   # dark asphalt
        cv2.circle(frame, (560, 50), 18, (210, 215, 220), -1)  # moon
    else:
        frame[:140, :] = (225, 195, 145)  # daytime sky (BGR)
        frame[140:, :] = (95, 100, 105)   # pavement
        cv2.line(frame, (0, 250), (w, 250), (190, 190, 190), 2)

    # Perimeter fence & gate posts
    for x in range(20, w, 60):
        cv2.rectangle(frame, (x, 110), (x + 6, 175), (70, 75, 80), -1)
    cv2.line(frame, (0, 130), (w, 130), (110, 115, 120), 2)
    cv2.line(frame, (0, 160), (w, 160), (110, 115, 120), 2)

    if label:
        cv2.rectangle(frame, (8, 8), (340, 34), (15, 20, 30), -1)
        cv2.putText(frame, label, (14, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (235, 240, 245), 1, cv2.LINE_AA)
    return frame


def _draw_blue_truck(frame: np.ndarray, x: int, y: int) -> None:
    # Pickup truck body (bright blue in BGR: (200, 80, 30))
    cv2.rectangle(frame, (x, y + 25), (x + 170, y + 75), (205, 85, 25), -1)
    cv2.rectangle(frame, (x + 25, y), (x + 110, y + 32), (220, 105, 40), -1)
    # Cab window
    cv2.rectangle(frame, (x + 35, y + 6), (x + 95, y + 25), (210, 225, 235), -1)
    # Wheels
    cv2.circle(frame, (x + 38, y + 78), 16, (25, 25, 25), -1)
    cv2.circle(frame, (x + 135, y + 78), 16, (25, 25, 25), -1)
    cv2.circle(frame, (x + 38, y + 78), 7, (170, 170, 170), -1)
    cv2.circle(frame, (x + 135, y + 78), 7, (170, 170, 170), -1)


def _draw_person(frame: np.ndarray, x: int, y: int, jacket_bgr=(40, 45, 200)) -> None:
    # Head
    cv2.circle(frame, (x, y), 11, (190, 205, 225), -1)
    # Torso
    cv2.rectangle(frame, (x - 14, y + 12), (x + 14, y + 58), jacket_bgr, -1)
    # Legs
    cv2.rectangle(frame, (x - 12, y + 58), (x - 2, y + 98), (45, 45, 55), -1)
    cv2.rectangle(frame, (x + 2, y + 58), (x + 12, y + 98), (45, 45, 55), -1)


def generate_sample_media(output_dir: Path | None = None) -> dict[str, Path]:
    """Create synthetic test images and a 16-second MP4 patrol video."""
    out = output_dir or SAMPLE_MEDIA_DIR
    out.mkdir(parents=True, exist_ok=True)

    # Image 1: Blue pickup truck near garage
    img1 = _draw_scene_background(night=False, label="CAM-DRONE | GARAGE | 12:00:05")
    _draw_blue_truck(img1, 210, 195)
    p1 = out / "garage_blue_truck.jpg"
    cv2.imwrite(str(p1), img1)

    # Image 2: Midnight person near main gate
    img2 = _draw_scene_background(night=True, label="CAM-DRONE | MAIN GATE | 00:01:15")
    _draw_person(img2, 320, 195, jacket_bgr=(50, 180, 220))
    p2 = out / "gate_midnight_person.jpg"
    cv2.imwrite(str(p2), img2)

    # Image 3: Restricted zone intruder
    img3 = _draw_scene_background(night=False, label="CAM-DRONE | RESTRICTED ZONE | 14:12:00")
    cv2.putText(img3, "RESTRICTED", (470, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (40, 40, 235), 2)
    _draw_person(img3, 280, 190, jacket_bgr=(35, 35, 210))
    p3 = out / "restricted_zone_intruder.jpg"
    cv2.imwrite(str(p3), img3)

    # 16s MP4 patrol video at 10 fps (160 frames)
    # 0-4s: Blue pickup enters Main Gate
    # 4-8s: Clear driveway
    # 8-12s: Person walking across perimeter
    # 12-16s: Blue pickup reappears near Garage
    video_path = out / "property_patrol_demo.mp4"
    fps = 10.0
    writer = cv2.VideoWriter(
        str(video_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (640, 360),
    )
    try:
        for i in range(160):
            sec = i / fps
            if sec < 4.0:
                frame = _draw_scene_background(night=False, label=f"PATROL | MAIN GATE | +{sec:04.1f}s")
                x_pos = int(40 + sec * 75)
                _draw_blue_truck(frame, x_pos, 200)
            elif sec < 8.0:
                frame = _draw_scene_background(night=False, label=f"PATROL | DRIVEWAY CLEAR | +{sec:04.1f}s")
            elif sec < 12.0:
                frame = _draw_scene_background(night=False, label=f"PATROL | PERIMETER | +{sec:04.1f}s")
                px = int(140 + (sec - 8.0) * 85)
                _draw_person(frame, px, 190, jacket_bgr=(45, 55, 210))
            else:
                frame = _draw_scene_background(night=False, label=f"PATROL | GARAGE | +{sec:04.1f}s")
                x_pos = int(380 - (sec - 12.0) * 55)
                _draw_blue_truck(frame, x_pos, 198)
            writer.write(frame)
    finally:
        writer.release()

    return {
        "garage_blue_truck": p1,
        "gate_midnight_person": p2,
        "restricted_zone_intruder": p3,
        "property_patrol_demo": video_path,
    }


if __name__ == "__main__":
    created = generate_sample_media()
    for name, path in created.items():
        print(f"Generated {name}: {path} ({path.stat().st_size} bytes)")
