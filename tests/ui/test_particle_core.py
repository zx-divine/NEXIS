import math
from time import perf_counter
from threading import Event
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, Signal

from nexis.ui.main_window import MainWindow
from nexis.ui.reactor import ReactorState, ReactorWidget, fibonacci_sphere
from nexis.ui.themes import apply


@pytest.mark.parametrize("count", [200, 340, 400])
def test_balanced_fibonacci_surface(count):
    points = fibonacci_sphere(count)
    assert len(points) == count and len(set(points)) == count
    assert all(math.isclose(x*x + y*y + z*z, 1., abs_tol=1e-12) for x, y, z in points)
    assert all(abs(sum(p[axis] for p in points) / count) < .01 for axis in range(3))
    assert points[0][1] == 1. and points[-1][1] == -1.


def test_projection_is_finite_depth_sorted_and_bounded_during_transitions(qtbot):
    core = ReactorWidget()
    qtbot.addWidget(core)
    core.show()
    assert len(core.particles) == 340
    for state in ReactorState:
        core.set_state(state)
        for _ in range(40):
            core.set_audio_level(1.)
            core.advance_motion(.033, perf_counter())
            projected = core.projected_particles()
            assert len(projected) == 340
            assert projected[0][0] < 0 < projected[-1][0]
            assert [p[0] for p in projected] == sorted(p[0] for p in projected)
            assert all(math.isfinite(n) for p in projected for n in p)
            assert max(math.hypot(p[1], p[2]) for p in projected) < 1.22
        assert not core.grab().isNull()


def test_audio_smoothing_expiry_mute_and_reduced_motion(qtbot):
    core = ReactorWidget()
    qtbot.addWidget(core)
    core.set_state("LISTENING")
    now = perf_counter()
    core.set_audio_level(1.)
    core.advance_motion(.05, now)
    assert 0 < core.smoothed_amplitude < 1
    peak = core.smoothed_amplitude
    core.set_audio_level(0.)
    core.advance_motion(.05, now)
    assert 0 < core.smoothed_amplitude < peak
    core.set_audio_level(float("nan"))
    assert core.audio_level is None
    core.set_audio_level(1.)
    core.advance_motion(.05, now + 1)
    assert core.smoothed_amplitude < peak
    core.set_state("MUTED")
    core.set_audio_level(1.)
    assert core.smoothed_amplitude == 0 and core.audio_level is None
    core.set_reduced_motion(True)
    first = core.projected_particles()
    core.set_audio_level(1.)
    assert core.projected_particles() == first and not core.timer.isActive()


@pytest.mark.parametrize("theme", ["og", "midnight", "arctic", "cyber", "matrix", "custom"])
def test_theme_and_resize_cache(qtbot, theme):
    core = ReactorWidget()
    qtbot.addWidget(core)
    apply(theme)
    core.set_reduced_motion(True)
    for size in (220, 340, 700):
        core.resize(size, size)
        assert not core.grab().isNull()
        assert core.static_geometry(size).devicePixelRatio() == core.devicePixelRatioF()


class Speech(QObject):
    playback_started = Signal(str)
    playback_finished = Signal(str, str)
    finished = Signal()


def test_actual_playback_precedence_and_stale_events(qtbot, db, tmp_path, platform):
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    service = Speech()
    voice = window.voice
    voice.attach_speech(service)
    voice.speech_id = "current"
    voice.speech_generation = voice.turn.generation
    voice.change_state("SPEAKING")
    assert window.reactor.state == ReactorState.PROCESSING
    service.playback_started.emit("old")
    assert window.reactor.state == ReactorState.PROCESSING
    service.playback_started.emit("current")
    assert window.reactor.state == ReactorState.SPEAKING
    window.settle_state()
    assert window.reactor.state == ReactorState.SPEAKING
    window.set_state("WAITING_PERMISSION")
    assert window.reactor.state == ReactorState.WAITING_PERMISSION
    service.playback_finished.emit("current", "PASS")
    assert window.reactor.state == ReactorState.IDLE
    voice.stop()
    service.playback_started.emit("current")
    assert window.reactor.state == ReactorState.IDLE
    window.set_microphone_muted(True)
    voice.capture_active = True
    voice.audio_level(1.)
    window.set_state("LISTENING")
    assert window.reactor.state == ReactorState.MUTED
    assert window.reactor.audio_level is None
    window.close()


def test_preparing_capture_does_not_claim_active_listening(qtbot, db, tmp_path, platform):
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    window.voice.turn.begin()
    window.voice.change_state("LISTENING")
    assert window.reactor.state == ReactorState.PROCESSING
    window.voice.voice_status("LISTENING — microphone active")
    assert window.reactor.state == ReactorState.LISTENING
    window.voice.voice_status("TRANSCRIBING — microphone off")
    assert window.reactor.state == ReactorState.PROCESSING
    assert not window.voice.capture_active
    window.close()


def test_shutdown_clears_listening_while_waiting_for_background_work(qtbot, db, tmp_path, platform):
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    window.show()
    running = [True]
    job = SimpleNamespace(cancel=Event(), isRunning=lambda: running[0])
    window.background_jobs = lambda: [job]
    window.voice.capture_active = True
    window.set_state("LISTENING")
    assert window.reactor.state == ReactorState.LISTENING
    window.close()
    assert window.isVisible() and job.cancel.is_set()
    for core in (window.reactor, window.voice.reactor, window.welcome.reactor):
        assert core.state != ReactorState.LISTENING
        assert not core.timer.isActive() and core.audio_level is None
    running[0] = False
    qtbot.waitUntil(lambda: not window.isVisible())


def test_chat_reply_and_cancellation_do_not_leave_stale_thinking(qtbot, db, tmp_path, platform):
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    job = SimpleNamespace(cancel=Event(), isRunning=lambda: True)
    window.ai_jobs = [job]
    window.current_ai = job
    window.set_state("PROCESSING")
    window.settle_state()
    assert window.reactor.state == ReactorState.PROCESSING
    window.ai_reply("Completed response before worker cleanup", "chat")
    assert window.reactor.state == ReactorState.IDLE
    window.set_state("PROCESSING")
    window.chat.cancel_ai()
    assert job.cancel.is_set() and window.reactor.state == ReactorState.IDLE
    window.set_state("PROCESSING")
    window.online_finished(job, "chat")
    assert window.reactor.state == ReactorState.IDLE
    assert not window.ai_jobs and window.current_ai is None
    window.close()


def test_manual_stop_and_escape_clear_cancelled_activity(qtbot, db, tmp_path, platform):
    window = MainWindow(db, tmp_path, platform)
    qtbot.addWidget(window)
    decisions = []
    worker = SimpleNamespace(cancel=Event(), isRunning=lambda: True, respond=decisions.append)
    window.worker = worker
    window.set_state("EXECUTING")
    window.stop_command()
    assert worker.cancel.is_set() and decisions == [False]
    assert window.reactor.state == ReactorState.IDLE
    window.worker = None
    job = SimpleNamespace(cancel=Event(), isRunning=lambda: True)
    window.ai_jobs = [job]
    window.set_state("PROCESSING")
    window.escape_action()
    assert job.cancel.is_set() and window.reactor.state == ReactorState.IDLE
    window.ai_jobs.clear()
    window.close()
