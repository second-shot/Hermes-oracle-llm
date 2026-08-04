from __future__ import annotations

import errno
import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from hermes_growth import storage as growth_storage
from hermes_growth.contracts import (
    FeedbackScope,
    FeedbackStatus,
    GrowthFeedback,
    GrowthObservation,
    ObservationKind,
    Reflection,
    RecommendedResponse,
    RiskClass,
)
from hermes_growth.feedback import FeedbackStore, growth_status
from hermes_growth.gap_detector import GapDetector
from hermes_growth.observations import ObservationStore
from hermes_growth.reflection import ReflectionStore


def observation(
    observation_id: str,
    *,
    task_class: str = "resale.research",
    kind: ObservationKind = ObservationKind.FAILURE,
    corrected: bool = False,
    risk: RiskClass = RiskClass.SAFE,
    success: bool = False,
) -> GrowthObservation:
    return GrowthObservation(
        observation_id=observation_id,
        timestamp=datetime.now(UTC).isoformat(),
        project_id="hermes",
        task_id=f"task-{observation_id}",
        task_class=task_class,
        kind=kind,
        skill_id="resale-research",
        skill_version="1.0.0",
        expected_outcome="verified result",
        actual_outcome="incorrect result",
        success=success,
        confidence=0.4,
        retry_count=1,
        latency_ms=1500,
        operator_correction="use sold listings" if corrected else "",
        evidence=[f"audit:{observation_id}"],
        affected_modules=["resale"],
        risk_class=risk,
        provenance=["local:test"],
    )


def test_one_ordinary_failure_does_not_create_gap(tmp_path: Path) -> None:
    store = ObservationStore(tmp_path)
    store.append(observation("obs-1"))

    assert GapDetector(tmp_path).detect() == []


def test_three_related_failures_create_one_gap(tmp_path: Path) -> None:
    store = ObservationStore(tmp_path)
    for number in range(3):
        store.append(observation(f"obs-{number}"))

    gaps = GapDetector(tmp_path).detect()

    assert len(gaps) == 1
    assert gaps[0].supporting_observation_ids == ["obs-0", "obs-1", "obs-2"]
    assert gaps[0].frequency == 3
    assert gaps[0].recommended_response == RecommendedResponse.IMPROVE_SKILL


def test_failures_older_than_configured_window_do_not_create_gap(tmp_path: Path) -> None:
    store = ObservationStore(tmp_path)
    stale_timestamp = (datetime.now(UTC) - timedelta(days=31)).isoformat()
    for number in range(3):
        store.append(replace(observation(f"stale-{number}"), timestamp=stale_timestamp))

    assert GapDetector(tmp_path).detect() == []


def test_growth_status_excludes_stale_failure_clusters(tmp_path: Path) -> None:
    store = ObservationStore(tmp_path)
    stale_timestamp = (datetime.now(UTC) - timedelta(days=31)).isoformat()
    for number in range(3):
        store.append(replace(observation(f"stale-status-{number}"), timestamp=stale_timestamp))

    status = growth_status(tmp_path)

    assert status["repeated_failure_clusters"] == []
    assert status["open_gaps"] == []


def test_repeated_missing_skill_recommends_new_skill_without_generating_it(tmp_path: Path) -> None:
    store = ObservationStore(tmp_path)
    for number in range(3):
        store.append(observation(f"missing-{number}", kind=ObservationKind.MISSING_SKILL))

    gap = GapDetector(tmp_path).detect()[0]

    assert gap.recommended_response == RecommendedResponse.NEW_SKILL


def test_unrelated_failures_are_kept_in_separate_clusters(tmp_path: Path) -> None:
    store = ObservationStore(tmp_path)
    for prefix, task_class in (("research", "resale.research"), ("docs", "docs.summary")):
        for number in range(3):
            store.append(observation(f"{prefix}-{number}", task_class=task_class))

    gaps = GapDetector(tmp_path).detect()

    assert len(gaps) == 2
    assert {gap.task_cluster for gap in gaps} == {"resale.research", "docs.summary"}


def test_two_explicit_corrections_create_one_gap(tmp_path: Path) -> None:
    store = ObservationStore(tmp_path)
    store.append(observation("correction-1", corrected=True))
    store.append(observation("correction-2", corrected=True))

    gaps = GapDetector(tmp_path).detect()

    assert len(gaps) == 1
    assert gaps[0].frequency == 2
    assert "operator corrections" in gaps[0].justification


def test_gap_support_includes_all_related_observations_when_corrections_trigger(tmp_path: Path) -> None:
    store = ObservationStore(tmp_path)
    store.append(observation("mixed-1", corrected=True))
    store.append(observation("mixed-2", corrected=True))
    store.append(observation("mixed-3"))

    gap = GapDetector(tmp_path).detect()[0]

    assert gap.supporting_observation_ids == ["mixed-1", "mixed-2", "mixed-3"]
    assert gap.frequency == 3
    assert gap.evidence == ["audit:mixed-1", "audit:mixed-2", "audit:mixed-3"]


def test_correction_kind_counts_as_explicit_correction(tmp_path: Path) -> None:
    items = [
        observation(f"kind-{number}", kind=ObservationKind.OPERATOR_CORRECTION)
        for number in range(2)
    ]

    assert len(GapDetector(tmp_path).detect(items)) == 1


def test_successful_correction_kind_qualifies_without_correction_text(tmp_path: Path) -> None:
    items = [
        observation(
            f"successful-kind-{number}",
            kind=ObservationKind.OPERATOR_CORRECTION,
            success=True,
        )
        for number in range(2)
    ]

    gap = GapDetector(tmp_path).detect(items)

    assert len(gap) == 1
    assert gap[0].supporting_observation_ids == ["successful-kind-0", "successful-kind-1"]


def test_duplicate_observation_ids_do_not_inflate_evidence(tmp_path: Path) -> None:
    store = ObservationStore(tmp_path)
    first = observation("same")
    store.append(first)
    store.append(first)
    store.append(observation("second"))

    assert len(store.history()) == 3
    assert [item.observation_id for item in store.observations()] == ["same", "second"]
    assert GapDetector(tmp_path).detect() == []


def test_critical_structural_regression_creates_immediate_gap(tmp_path: Path) -> None:
    ObservationStore(tmp_path).append(
        observation(
            "structural-1",
            kind=ObservationKind.STRUCTURAL_REGRESSION,
            risk=RiskClass.PRIVILEGED,
        )
    )

    gaps = GapDetector(tmp_path).detect()

    assert len(gaps) == 1
    assert gaps[0].recommended_response == RecommendedResponse.STRUCTURAL_REPAIR
    assert gaps[0].severity == "critical"


def test_observation_store_is_append_only(tmp_path: Path) -> None:
    store = ObservationStore(tmp_path)
    store.append(observation("first"))
    initial = store.path.read_text(encoding="utf-8")
    store.append(observation("second"))

    assert store.path.read_text(encoding="utf-8").startswith(initial)
    assert len(store.path.read_text(encoding="utf-8").splitlines()) == 2


def test_jsonl_stores_serialize_concurrent_writers(tmp_path: Path) -> None:
    observations = ObservationStore(tmp_path)
    reflections = ReflectionStore(tmp_path)
    feedback = FeedbackStore(tmp_path)

    def append_all(number: int) -> None:
        observations.append(observation(f"concurrent-{number}"))
        reflections.append(
            Reflection(
                reflection_id=f"reflection-{number}",
                timestamp="2026-08-04T13:00:00+00:00",
                project_id="hermes",
                task_id=f"task-{number}",
                intended_result="serialize writes",
                actual_result="record retained",
                evidence_references=[f"concurrent-{number}"],
                worked=[],
                failed=[],
                disproved_assumptions=[],
                corrections=[],
                reusable_lessons=[],
                change_type=RecommendedResponse.NO_CHANGE,
                next_checkpoint="continue",
            )
        )
        feedback.append(
            GrowthFeedback(
                feedback_id=f"feedback-{number}",
                timestamp="2026-08-04T14:00:00+00:00",
                status=FeedbackStatus.ACCEPTED,
                contributor="operator-a",
                project_id="hermes",
                task_id=f"task-{number}",
                skill_id="resale-research",
                skill_version="1.0.0",
                concrete_correction="retain record",
                reason="concurrency test",
                evidence=[f"task-{number}:review"],
                scope=FeedbackScope.TASK,
            )
        )
        observations.history()
        reflections.reflections()
        feedback.history()

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(append_all, range(24)))

    assert len(observations.history()) == 24
    assert len(reflections.reflections()) == 24
    assert len(feedback.history()) == 24
    assert (tmp_path / ".growth.lock").is_file()


def test_jsonl_stores_serialize_concurrent_process_writers(tmp_path: Path) -> None:
    script = """
import json
import sys
from hermes_growth.contracts import GrowthFeedback, GrowthObservation, Reflection
from hermes_growth.feedback import FeedbackStore
from hermes_growth.observations import ObservationStore
from hermes_growth.reflection import ReflectionStore
root = sys.argv[1]
ObservationStore(root).append(GrowthObservation.from_dict(json.loads(sys.argv[2])))
ReflectionStore(root).append(Reflection.from_dict(json.loads(sys.argv[3])))
FeedbackStore(root).append(GrowthFeedback.from_dict(json.loads(sys.argv[4])))
"""
    processes = []
    for number in range(4):
        reflection = Reflection(
            reflection_id=f"process-reflection-{number}",
            timestamp="2026-08-04T13:00:00+00:00",
            project_id="hermes",
            task_id=f"process-task-{number}",
            intended_result="serialize process writes",
            actual_result="record retained",
            evidence_references=[f"process-{number}"],
            worked=[],
            failed=[],
            disproved_assumptions=[],
            corrections=[],
            reusable_lessons=[],
            change_type=RecommendedResponse.NO_CHANGE,
            next_checkpoint="continue",
        )
        feedback = GrowthFeedback(
            feedback_id=f"process-feedback-{number}",
            timestamp="2026-08-04T14:00:00+00:00",
            status=FeedbackStatus.ACCEPTED,
            contributor="operator-a",
            project_id="hermes",
            task_id=f"process-task-{number}",
            skill_id="resale-research",
            skill_version="1.0.0",
            concrete_correction="retain record",
            reason="process concurrency test",
            evidence=[f"process-task-{number}:review"],
            scope=FeedbackScope.TASK,
        )
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    script,
                    str(tmp_path),
                    json.dumps(observation(f"process-{number}").to_dict()),
                    json.dumps(reflection.to_dict()),
                    json.dumps(feedback.to_dict()),
                ],
                cwd=Path(__file__).resolve().parents[1],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        )

    for process in processes:
        stdout, stderr = process.communicate(timeout=20)
        assert process.returncode == 0, f"{stdout}\n{stderr}"

    assert len(ObservationStore(tmp_path).history()) == 4
    assert len(ReflectionStore(tmp_path).reflections()) == 4
    assert len(FeedbackStore(tmp_path).history()) == 4


def test_observation_store_rejects_missing_required_audit_fields(tmp_path: Path) -> None:
    incomplete = replace(observation("missing-evidence"), evidence=[], provenance=[])

    with pytest.raises(ValueError, match="evidence is required; provenance is required"):
        ObservationStore(tmp_path).append(incomplete)

    assert not ObservationStore(tmp_path).path.exists()


def test_observation_store_requires_skill_module_and_nonblank_evidence(tmp_path: Path) -> None:
    incomplete = replace(
        observation("missing-context"),
        skill_id="",
        skill_version="",
        affected_modules=[],
        evidence=[" "],
        provenance=[" "],
    )

    with pytest.raises(ValueError, match="skill_id is required"):
        ObservationStore(tmp_path).append(incomplete)


def test_reflection_references_evidence_without_rewriting_observations(tmp_path: Path) -> None:
    observations = ObservationStore(tmp_path)
    observations.append(observation("obs-1"))
    before = observations.path.read_bytes()
    reflection = Reflection(
        reflection_id="reflection-1",
        timestamp="2026-08-04T13:00:00+00:00",
        project_id="hermes",
        task_id="checkpoint-b",
        intended_result="add observation loop",
        actual_result="focused tests passed",
        evidence_references=["obs-1", "pytest:test_growth_observation"],
        worked=["append-only storage"],
        failed=[],
        disproved_assumptions=[],
        corrections=[],
        reusable_lessons=["deduplicate analysis views"],
        change_type=RecommendedResponse.IMPROVE_SKILL,
        next_checkpoint="run regression suite",
    )

    ReflectionStore(tmp_path).append(reflection)

    assert observations.path.read_bytes() == before
    assert ReflectionStore(tmp_path).reflections()[0].evidence_references[0] == "obs-1"


def test_reflection_rejects_missing_required_outcome(tmp_path: Path) -> None:
    item = Reflection(
        reflection_id="reflection-empty",
        timestamp="2026-08-04T13:00:00+00:00",
        project_id="hermes",
        task_id="checkpoint-b",
        intended_result="",
        actual_result="focused tests passed",
        evidence_references=["pytest:test_growth_observation"],
        worked=[],
        failed=[],
        disproved_assumptions=[],
        corrections=[],
        reusable_lessons=[],
        change_type=RecommendedResponse.NO_CHANGE,
        next_checkpoint="run regression suite",
    )

    with pytest.raises(ValueError, match="intended_result is required"):
        ReflectionStore(tmp_path).append(item)


def test_feedback_requires_concrete_evidence_for_every_scope(tmp_path: Path) -> None:
    item = GrowthFeedback(
        feedback_id="feedback-empty",
        timestamp="2026-08-04T14:00:00+00:00",
        status=FeedbackStatus.ACCEPTED,
        contributor="operator-a",
        project_id="hermes",
        task_id="task-1",
        skill_id="resale-research",
        skill_version="1.0.0",
        concrete_correction="use sold listings",
        reason="asking prices are not completed sales",
        evidence=[],
        scope=FeedbackScope.TASK,
    )

    with pytest.raises(ValueError, match="evidence is required"):
        FeedbackStore(tmp_path).append(item)


def test_feedback_requires_skill_identity_in_api_and_cli(tmp_path: Path) -> None:
    item = GrowthFeedback(
        feedback_id="feedback-no-skill",
        timestamp="2026-08-04T14:00:00+00:00",
        status=FeedbackStatus.ACCEPTED,
        contributor="operator-a",
        project_id="hermes",
        task_id="task-1",
        skill_id="",
        skill_version="",
        concrete_correction="use sold listings",
        reason="review",
        evidence=["task-1:review"],
        scope=FeedbackScope.TASK,
    )
    with pytest.raises(ValueError, match="skill_id is required; skill_version is required"):
        FeedbackStore(tmp_path).append(item)

    env = os.environ.copy()
    env["HERMES_DATA_DIR"] = str(tmp_path / "runtime")
    result = subprocess.run(
        [
            sys.executable,
            "hermes_employee.py",
            "growth",
            "feedback",
            "--status",
            "accepted",
            "--contributor",
            "operator-a",
            "--project",
            "hermes",
            "--task",
            "task-1",
            "--correction",
            "use sold listings",
            "--reason",
            "review",
            "--evidence",
            "task-1:review",
            "--scope",
            "task",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "--skill" in result.stderr
    assert "--version" in result.stderr


def test_feedback_scope_is_preserved(tmp_path: Path) -> None:
    item = GrowthFeedback(
        feedback_id="feedback-1",
        timestamp="2026-08-04T14:00:00+00:00",
        status=FeedbackStatus.ACCEPTED,
        contributor="operator-a",
        project_id="hermes",
        task_id="task-1",
        skill_id="resale-research",
        skill_version="1.0.0",
        concrete_correction="use sold listings",
        reason="asking prices are not completed sales",
        evidence=["task-1:review"],
        scope=FeedbackScope.PROJECT,
    )

    FeedbackStore(tmp_path).append(item)

    assert FeedbackStore(tmp_path).feedback()[0].scope == FeedbackScope.PROJECT


def test_one_contributor_cannot_automatically_create_global_rule(tmp_path: Path) -> None:
    project_item = GrowthFeedback(
        feedback_id="feedback-1",
        timestamp="2026-08-04T14:00:00+00:00",
        status=FeedbackStatus.CORRECTED,
        contributor="operator-a",
        project_id="hermes",
        task_id="task-1",
        skill_id="resale-research",
        skill_version="1.0.0",
        concrete_correction="always prefer my formatting",
        reason="personal preference",
        evidence=["task-1:comment"],
        scope=FeedbackScope.GLOBAL,
    )

    with pytest.raises(PermissionError, match="global feedback requires explicit operator approval"):
        FeedbackStore(tmp_path).append(project_item)

    FeedbackStore(tmp_path).append(replace(project_item, operator_approved=True))
    assert FeedbackStore(tmp_path).feedback()[0].scope == FeedbackScope.GLOBAL


def test_superseded_feedback_is_not_reported_as_unresolved(tmp_path: Path) -> None:
    item = GrowthFeedback(
        feedback_id="feedback-1",
        timestamp="2026-08-04T14:00:00+00:00",
        status=FeedbackStatus.CORRECTED,
        contributor="operator-a",
        project_id="hermes",
        task_id="task-1",
        skill_id="resale-research",
        skill_version="1.0.0",
        concrete_correction="use sold listings",
        reason="review",
        evidence=["task-1:review"],
        scope=FeedbackScope.TASK,
    )
    store = FeedbackStore(tmp_path)
    store.append(item)
    store.append(replace(item, status=FeedbackStatus.SUPERSEDED))

    assert len(store.history()) == 2
    assert store.feedback()[0].status == FeedbackStatus.SUPERSEDED
    assert growth_status(tmp_path)["unresolved_corrections"] == []


@pytest.mark.parametrize(
    ("field_name", "different_value"),
    [
        ("project_id", "other-project"),
        ("task_id", "other-task"),
        ("skill_id", "other-skill"),
        ("skill_version", "2.0.0"),
        ("contributor", "operator-b"),
        ("scope", FeedbackScope.PROJECT),
    ],
)
def test_feedback_revision_rejects_identity_collision_and_keeps_correction_unresolved(
    tmp_path: Path, field_name: str, different_value: object
) -> None:
    item = GrowthFeedback(
        feedback_id="feedback-collision",
        timestamp="2026-08-04T14:00:00+00:00",
        status=FeedbackStatus.CORRECTED,
        contributor="operator-a",
        project_id="hermes",
        task_id="task-1",
        skill_id="resale-research",
        skill_version="1.0.0",
        concrete_correction="use sold listings",
        reason="review",
        evidence=["task-1:review"],
        scope=FeedbackScope.TASK,
    )
    store = FeedbackStore(tmp_path)
    store.append(item)

    with pytest.raises(ValueError, match="feedback identity fields are immutable"):
        store.append(replace(item, status=FeedbackStatus.SUPERSEDED, **{field_name: different_value}))

    assert growth_status(tmp_path)["unresolved_corrections"] == ["feedback-collision"]


def test_concurrent_gap_and_status_publication_is_atomic(tmp_path: Path) -> None:
    store = ObservationStore(tmp_path)
    for number in range(3):
        store.append(observation(f"gap-concurrent-{number}"))

    detector = GapDetector(tmp_path)
    operations = [detector.detect, lambda: growth_status(tmp_path)] * 12
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = [future.result() for future in [executor.submit(operation) for operation in operations]]

    assert len(results) == len(operations)
    payload = json.loads(detector.path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert len(payload["candidates"]) == 1
    assert list(tmp_path.glob("gap_candidates.*.tmp")) == []


def test_newer_status_cannot_be_overwritten_by_stale_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ObservationStore(tmp_path)
    store.append(observation("stale-1"))
    store.append(observation("stale-2"))
    stale_snapshot_ready = threading.Event()
    release_stale = threading.Event()
    newer_published = threading.Event()
    original_observations = ObservationStore.observations

    def ordered_observations(self: ObservationStore) -> list[GrowthObservation]:
        values = original_observations(self)
        if threading.current_thread().name == "stale-status":
            stale_snapshot_ready.set()
            assert release_stale.wait(timeout=5)
        return values

    monkeypatch.setattr(ObservationStore, "observations", ordered_observations)

    stale_thread = threading.Thread(
        target=lambda: growth_status(tmp_path), name="stale-status"
    )

    def publish_newer() -> None:
        store.append(observation("newest-3"))
        growth_status(tmp_path)
        newer_published.set()

    newer_thread = threading.Thread(target=publish_newer, name="newer-status")
    stale_thread.start()
    assert stale_snapshot_ready.wait(timeout=5)
    newer_thread.start()
    newer_published.wait(timeout=0.5)
    release_stale.set()
    stale_thread.join(timeout=5)
    newer_thread.join(timeout=5)

    assert not stale_thread.is_alive()
    assert not newer_thread.is_alive()
    assert len(GapDetector(tmp_path).candidates()) == 1


class _FakeLockHandle:
    def seek(self, _offset: int) -> None:
        return None

    def fileno(self) -> int:
        return 7


def test_windows_lock_retries_transient_contention_then_succeeds() -> None:
    attempts = 0

    def locking(_fd: int, _mode: int, _length: int) -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise OSError(errno.EACCES, "lock contention")

    growth_storage._acquire_windows_lock(
        _FakeLockHandle(),
        locking=locking,
        lock_mode=1,
        timeout=1.0,
        retry_interval=0.0,
    )

    assert attempts == 3


def test_windows_lock_propagates_permanent_error_immediately() -> None:
    attempts = 0

    def locking(_fd: int, _mode: int, _length: int) -> None:
        nonlocal attempts
        attempts += 1
        raise OSError(errno.EBADF, "bad handle")

    with pytest.raises(OSError, match="bad handle"):
        growth_storage._acquire_windows_lock(
            _FakeLockHandle(), locking=locking, lock_mode=1
        )

    assert attempts == 1


def test_windows_lock_contention_has_bounded_timeout() -> None:
    now = [0.0]
    attempts = 0

    def locking(_fd: int, _mode: int, _length: int) -> None:
        nonlocal attempts
        attempts += 1
        raise OSError(errno.EACCES, "lock contention")

    def sleep(duration: float) -> None:
        now[0] += duration

    with pytest.raises(TimeoutError, match="timed out acquiring growth lock"):
        growth_storage._acquire_windows_lock(
            _FakeLockHandle(),
            locking=locking,
            lock_mode=1,
            timeout=0.02,
            retry_interval=0.01,
            monotonic=lambda: now[0],
            sleeper=sleep,
        )

    assert attempts == 3


def test_growth_status_counts_failures_independently_of_correction_trigger(tmp_path: Path) -> None:
    store = ObservationStore(tmp_path)
    store.append(observation("failed-1", corrected=True))
    store.append(observation("failed-2", corrected=True))
    store.append(observation("failed-3"))

    assert growth_status(tmp_path)["repeated_failure_clusters"] == ["resale.research"]


def test_successful_corrections_are_not_repeated_failure_cluster(tmp_path: Path) -> None:
    store = ObservationStore(tmp_path)
    for number in range(3):
        store.append(observation(f"success-{number}", corrected=True, success=True))

    status = growth_status(tmp_path)

    assert len(status["open_gaps"]) == 1
    assert status["repeated_failure_clusters"] == []


def test_runtime_files_use_external_growth_root(tmp_path: Path) -> None:
    data_dir = tmp_path / "runtime"
    env = os.environ.copy()
    env["HERMES_DATA_DIR"] = str(data_dir)

    result = subprocess.run(
        [sys.executable, "hermes_employee.py", "growth", "status"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["observation_count"] == 0
    assert (data_dir / "growth").is_dir()
    assert not (Path(__file__).resolve().parents[1] / "observations.jsonl").exists()


def test_gap_detector_never_generates_skill_code(tmp_path: Path) -> None:
    store = ObservationStore(tmp_path)
    for number in range(3):
        store.append(observation(f"obs-{number}"))

    gap = GapDetector(tmp_path).detect()[0]
    payload = gap.to_dict()

    assert "code" not in payload
    assert "implementation" not in payload
    assert set(tmp_path.iterdir()) == {
        store.path,
        GapDetector(tmp_path).path,
        tmp_path / ".growth.lock",
    }
