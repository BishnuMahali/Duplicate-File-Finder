import os
import json
import hashlib
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import Duplicate_File_Finder as dff

@pytest.fixture
def temp_video_dir(tmp_path):
    video_dir = tmp_path / "videos"
    video_dir.mkdir()
    (video_dir / "test1.mp4").write_text("dummy video 1")
    (video_dir / "test2.mkv").write_text("dummy video 2")
    (video_dir / "readme.txt").write_text("not a video")
    subdir = video_dir / "subdir"
    subdir.mkdir()
    (subdir / "test3.avi").write_text("dummy video 3")
    return video_dir

def test_resolve_gpu_cpu():
    with patch("shutil.which", return_value=None):
        assert dff.resolve_gpu("cpu") == []
        assert dff.resolve_gpu("auto") == []

def test_resolve_gpu_cuda():
    assert dff.resolve_gpu("cuda") == ["-hwaccel", "cuda"]

def test_resolve_gpu_auto_with_nvidia():
    with patch("shutil.which", side_effect=lambda x: "/usr/bin/nvidia-smi" if x == "nvidia-smi" else None):
        assert dff.resolve_gpu("auto") == ["-hwaccel", "cuda"]

def test_find_videos_non_recursive(temp_video_dir):
    videos = dff.find_videos(temp_video_dir, recurse=False)
    assert len(videos) == 2
    names = {v.name for v in videos}
    assert names == {"test1.mp4", "test2.mkv"}

def test_find_videos_recursive(temp_video_dir):
    videos = dff.find_videos(temp_video_dir, recurse=True)
    assert len(videos) == 3
    names = {v.name for v in videos}
    assert names == {"test1.mp4", "test2.mkv", "test3.avi"}

def test_get_duration_success():
    mock_run = MagicMock()
    mock_run.stdout = b"123.45\n"
    with patch("subprocess.run", return_value=mock_run):
        duration = dff.get_duration("dummy.mp4")
        assert duration == 123.45

def test_get_duration_failure():
    with patch("subprocess.run", side_effect=Exception("error")):
        duration = dff.get_duration("dummy.mp4")
        assert duration is None

def test_quick_signature(tmp_path):
    test_file = tmp_path / "test.mp4"
    content = b"a" * (2 * 1024 * 1024)  # 2MB
    test_file.write_bytes(content)

    size, h = dff.quick_signature(test_file, chunk_size=1024)
    assert size == len(content)

    expected_h = hashlib.md5(content[:1024] + content[-1024:]).hexdigest()
    assert h == expected_h

def test_load_save_cache(tmp_path):
    cache_file = tmp_path / "cache.json"
    cache_data = {
        "path/to/video1": {"mtime": "123", "hashes": ["h1", "h2"]},
        "path/to/video2": {"mtime": "456", "hashes": ["h3"]}
    }

    # Test saving with existing paths
    v1 = tmp_path / "video1"
    v1.write_text("v1")
    v2 = tmp_path / "video2"
    v2.write_text("v2")

    real_cache_data = {
        str(v1): {"mtime": "123", "hashes": ["h1", "h2"]},
        str(v2): {"mtime": "456", "hashes": ["h3"]}
    }

    dff.save_cache(cache_file, real_cache_data)
    assert cache_file.exists()

    loaded_cache = dff.load_cache(cache_file)
    assert loaded_cache == real_cache_data

def test_load_corrupted_cache(tmp_path):
    cache_file = tmp_path / "corrupted.json"
    cache_file.write_text("invalid json")
    assert dff.load_cache(cache_file) == {}

def test_fingerprint(tmp_path):
    test_file = tmp_path / "test.mp4"
    test_file.write_text("video")

    def mock_run(cmd, **kwargs):
        # cmd looks like: [ffmpeg, -hwaccel, ..., -i, ..., -vf, ..., tmp/frame_%04d.jpg, ...]
        # The output path is the 3rd from the last normally, but it depends on hw_args.
        # Let's find it by looking for the argument that ends in frame_%04d.jpg
        out_pattern = next(arg for arg in cmd if "frame_%04d.jpg" in arg)
        out_dir = Path(out_pattern).parent
        (out_dir / "frame_0001.jpg").write_bytes(b"frame1")
        (out_dir / "frame_0002.jpg").write_bytes(b"frame2")
        return MagicMock()

    with patch("subprocess.run", side_effect=mock_run):
        hashes = dff.fingerprint(test_file, "ffmpeg", [], "1/10")
        assert len(hashes) == 2
        assert hashes[0] == hashlib.md5(b"frame1").hexdigest()
        assert hashes[1] == hashlib.md5(b"frame2").hexdigest()
