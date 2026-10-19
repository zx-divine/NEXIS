"""Explicit generation-aware voice turn state machine."""

from enum import Enum


class VoiceState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    TRANSCRIBING = "TRANSCRIBING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


class VoiceTurn:
    transitions = {
        VoiceState.IDLE: {
            VoiceState.LISTENING,
            VoiceState.THINKING,
            VoiceState.SPEAKING,
            VoiceState.ERROR,
            VoiceState.CANCELLED,
        },
        VoiceState.LISTENING: {VoiceState.TRANSCRIBING, VoiceState.ERROR, VoiceState.CANCELLED},
        VoiceState.TRANSCRIBING: {
            VoiceState.THINKING,
            VoiceState.IDLE,
            VoiceState.ERROR,
            VoiceState.CANCELLED,
        },
        VoiceState.THINKING: {
            VoiceState.SPEAKING,
            VoiceState.IDLE,
            VoiceState.ERROR,
            VoiceState.CANCELLED,
        },
        VoiceState.SPEAKING: {VoiceState.IDLE, VoiceState.ERROR, VoiceState.CANCELLED},
        VoiceState.ERROR: {
            VoiceState.IDLE,
            VoiceState.LISTENING,
            VoiceState.THINKING,
            VoiceState.SPEAKING,
            VoiceState.CANCELLED,
        },
        VoiceState.CANCELLED: {
            VoiceState.IDLE,
            VoiceState.LISTENING,
            VoiceState.THINKING,
            VoiceState.ERROR,
        },
    }

    def __init__(self):
        self.state = VoiceState.IDLE
        self.generation = 0

    def begin(self):
        if self.state in {
            VoiceState.LISTENING,
            VoiceState.TRANSCRIBING,
            VoiceState.THINKING,
            VoiceState.SPEAKING,
        }:
            raise ValueError("A voice turn is already active.")
        self.generation += 1
        self.state = VoiceState.LISTENING
        return self.generation

    def change(self, state, generation=None):
        if generation is not None and generation != self.generation:
            return False
        state = VoiceState(state)
        if state != self.state and state not in self.transitions[self.state]:
            raise ValueError("Invalid voice state transition.")
        self.state = state
        return True

    def cancel(self):
        self.generation += 1
        self.state = VoiceState.CANCELLED
