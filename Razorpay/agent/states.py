"""Agent state definitions and transition logic."""

from enum import Enum

class AgentState(str, Enum):
    IDLE = 'IDLE'
    SCANNING = 'SCANNING'
    EVALUATING = 'EVALUATING'
    PURCHASING = 'PURCHASING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    SHUTDOWN = 'SHUTDOWN'

# Valid transitions dict
VALID_TRANSITIONS: dict[AgentState, list[AgentState]] = {
    AgentState.IDLE: [AgentState.SCANNING, AgentState.SHUTDOWN],
    AgentState.SCANNING: [AgentState.EVALUATING, AgentState.FAILED, AgentState.SHUTDOWN],
    AgentState.EVALUATING: [AgentState.PURCHASING, AgentState.IDLE, AgentState.SHUTDOWN],
    AgentState.PURCHASING: [AgentState.COMPLETED, AgentState.FAILED, AgentState.SHUTDOWN],
    AgentState.COMPLETED: [AgentState.IDLE, AgentState.SHUTDOWN],
    AgentState.FAILED: [AgentState.IDLE, AgentState.SHUTDOWN],
    AgentState.SHUTDOWN: [],
}

def validate_transition(current: AgentState, target: AgentState) -> bool:
    """Validate if a state transition is allowed."""
    return target in VALID_TRANSITIONS.get(current, [])

class InvalidStateTransition(Exception):
    """Exception raised for invalid state transitions."""
    def __init__(self, current: AgentState, target: AgentState):
        super().__init__(f'Invalid transition: {current} -> {target}')
        self.current = current
        self.target = target
