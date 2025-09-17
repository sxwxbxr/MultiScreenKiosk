from datetime import datetime

from utils.content_schedule import ContentScheduler, compute_slot_assignments
from utils.config_loader import PaneSchedule, ScheduleBlock


def _dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2024, 1, 1, hour, minute)


def test_content_scheduler_matches_active_block():
    schedule = PaneSchedule(
        pane=0,
        default_source="News",
        blocks=[
            ScheduleBlock(start="08:00", end="12:00", source="Weather"),
            ScheduleBlock(start="12:00", end="18:00", source="Stocks"),
        ],
    )
    scheduler = ContentScheduler([schedule], now_provider=lambda: _dt(9, 30))
    assert scheduler.current_assignments() == {0: "Weather"}

    afternoon = scheduler.current_assignments(now=_dt(15, 0))
    assert afternoon == {0: "Stocks"}

    evening = scheduler.current_assignments(now=_dt(19, 0))
    assert evening == {0: "News"}


def test_content_scheduler_wraps_midnight():
    schedule = PaneSchedule(
        pane=1,
        default_source="Day",
        blocks=[ScheduleBlock(start="22:00", end="02:00", source="Night")],
    )
    scheduler = ContentScheduler([schedule])
    assert scheduler.current_assignments(now=_dt(23, 0)) == {1: "Night"}
    assert scheduler.current_assignments(now=_dt(1, 30)) == {1: "Night"}
    assert scheduler.current_assignments(now=_dt(8, 0)) == {1: "Day"}


def test_compute_slot_assignments_resolves_conflicts():
    assignments = {0: "B", 1: "A", 2: "unknown"}
    name_to_index = {"A": 0, "B": 1, "C": 2}
    indices, conflicts = compute_slot_assignments(3, assignments, name_to_index)
    assert indices[0] == 1
    assert indices[1] == 0
    assert len(conflicts) == 1
    assert conflicts[0][0] == 2
    assert conflicts[0][2] == "unknown source"


def test_compute_slot_assignments_fills_unused_slots():
    assignments = {0: "C"}
    name_to_index = {"A": 0, "B": 1, "C": 2}
    indices, conflicts = compute_slot_assignments(3, assignments, name_to_index)
    assert indices[0] == 2
    assert set(indices) == {0, 1, 2}
    assert conflicts
