from array import array
import pytest
from nexis.core.voice import audio_level, setup_status
from nexis.platform.system import SystemSampler


def test_audio_levels_are_from_pcm():
    assert audio_level(b"\x00" * 32) == 0
    assert audio_level(array("h", [16384, -16384]).tobytes()) == pytest.approx(0.5)
    assert audio_level(array("h", [-32768] * 8).tobytes()) == 1
    assert audio_level(b"x") == 0


def test_voice_setup_is_explicit(monkeypatch, tmp_path):
    monkeypatch.setattr("nexis.core.voice.importlib.util.find_spec", lambda name: None)
    ready, message = setup_status(str(tmp_path))
    assert not ready and "install" in message and "No models are downloaded" in message
    monkeypatch.setattr("nexis.core.voice.importlib.util.find_spec", lambda name: object())
    assert not setup_status(str(tmp_path))[0]
    (tmp_path / "am").mkdir()
    (tmp_path / "am/final.mdl").touch()
    assert not setup_status(str(tmp_path))[0]  # Acoustic weights alone are incomplete.
    for relative in ("conf/model.conf", "graph/HCLr.fst", "graph/Gr.fst"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    assert setup_status(str(tmp_path))[0]


def test_missing_system_sensors_are_na():
    sampler = SystemSampler()
    sampler.kernel = None
    sample = sampler.sample()
    assert sample.cpu is None and sample.memory is None and sample.uptime_seconds is None


def test_cpu_interval_math_uses_real_counter_deltas():
    class Kernel:
        index = 0

        def GetSystemTimes(self, *pointers):
            for pointer, value in zip(pointers, ((200, 300, 200), (210, 310, 210))[self.index]):
                pointer._obj.dwLowDateTime = value
            self.index += 1
            return 1

        def GlobalMemoryStatusEx(self, pointer):
            pointer._obj.load = 42
            pointer._obj.total = 8 * 1024**3
            return 1

        def GetTickCount64(self):
            return 100000

    sampler = SystemSampler()
    sampler.kernel = Kernel()
    assert sampler.sample().cpu is None
    result = sampler.sample()
    assert result.cpu == 50 and result.memory == 42 and result.total_memory_mb == 8192


def test_narrowband_default_is_not_passed_to_wideband_model(tmp_path):
    from nexis.core.voice import capture_rates

    config = tmp_path / "conf/mfcc.conf"
    config.parent.mkdir()
    config.write_text("--sample-frequency=16000\n--allow-downsample=true\n")
    assert capture_rates(tmp_path, 8000) == (16000, 48000, 44100)
    assert capture_rates(tmp_path, 48000)[0] == 48000
    config.write_text("--sample-frequency=8000\n")
    assert capture_rates(tmp_path, 8000)[0] == 8000
    config.write_text("--sample-frequency=16000\n--allow-upsample=true\n")
    assert capture_rates(tmp_path, 8000)[0] == 8000
