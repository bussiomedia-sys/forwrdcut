from forwrdcut.render.pipeline import _is_image


def test_is_image_detects_stills():
    for p in ["a.jpg", "b.JPEG", "c.png", "d.webp", "e.HEIC"]:
        assert _is_image(p)


def test_is_image_rejects_video():
    for p in ["a.mp4", "b.mov", "c.MP4", "d.mkv", "noext"]:
        assert not _is_image(p)
