from backend_mvp.lifecycle import Lifecycle, LifecycleManager, allowed_transitions


def test_allowed_transitions_map_contains_ready_to_starting() -> None:
    transitions = allowed_transitions()
    assert "starting" in transitions["ready"]


def test_valid_transition_sequence() -> None:
    mgr = LifecycleManager()
    mgr.transition(Lifecycle.PREPARING)
    mgr.transition(Lifecycle.READY)
    mgr.transition(Lifecycle.STARTING)
    mgr.transition(Lifecycle.RUNNING)
    assert mgr.snapshot().lifecycle == "running"


def test_invalid_transition_raises() -> None:
    mgr = LifecycleManager()
    try:
        mgr.transition(Lifecycle.RUNNING)
        assert False, "Expected invalid transition to raise"
    except ValueError:
        assert True


def test_duplicate_start_protection() -> None:
    mgr = LifecycleManager()
    mgr.transition(Lifecycle.PREPARING)
    mgr.transition(Lifecycle.READY)

    assert mgr.start_transition() is True
    assert mgr.start_transition() is False
    assert mgr.snapshot().lifecycle == "starting"
