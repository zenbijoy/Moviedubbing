import pytest

from aidub.domain.job import JobStatus, can_transition_job_status
from aidub.orchestration.state import JobState, JobStateMachine, TransitionError


def test_happy_path() -> None:
    machine = JobStateMachine()
    for state in (JobState.PREPARING, JobState.RUNNING, JobState.SUCCEEDED):
        machine.transition_to(state)
    assert machine.state is JobState.SUCCEEDED


def test_invalid_transition_is_rejected() -> None:
    machine = JobStateMachine()
    with pytest.raises(TransitionError):
        machine.transition_to(JobState.SUCCEEDED)


def test_failed_job_can_be_requeued() -> None:
    machine = JobStateMachine(JobState.FAILED)
    assert machine.transition_to(JobState.QUEUED) is JobState.QUEUED


@pytest.mark.parametrize("current", list(JobState))
@pytest.mark.parametrize("target", list(JobState))
def test_orchestration_transition_graph_is_the_domain_graph(
    current: JobStatus,
    target: JobStatus,
) -> None:
    machine = JobStateMachine(current)
    assert machine.can_transition_to(target) is can_transition_job_status(current, target)
