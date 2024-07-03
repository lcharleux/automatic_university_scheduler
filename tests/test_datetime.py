import pytest
import datetime
from datetime import datetime as dt
from automatic_university_scheduler.datetime import DateTime, TimeDelta, TimeInterval


class TestDateTime:
    @staticmethod
    def test_from_str():
        date_str = "2022-W01-1 00:00"
        dt_obj = DateTime.from_str(date_str)
        assert dt_obj.year == 2022
        assert dt_obj.isocalendar()[1] == 1
        assert dt_obj.isocalendar()[2] == 1
        assert dt_obj.hour == 0
        assert dt_obj.minute == 0

        date_str = "01/01/2022 00:00"
        dt_obj = DateTime.from_str(date_str)
        assert dt_obj.day == 1
        assert dt_obj.month == 1
        assert dt_obj.year == 2022
        assert dt_obj.hour == 0
        assert dt_obj.minute == 0

    @staticmethod
    def test_to_str():
        date_str = "01/01/2022 00:00"
        dt_obj = DateTime.from_str(date_str)
        assert dt_obj.to_str() == "2021-W52-6 00:00"
        assert dt_obj.to_str("dmy") == "01/01/2022 00:00"

    @staticmethod
    def test_from_datetime():
        dt_obj = dt(2022, 1, 1, 0, 0)
        dt_obj = DateTime.from_datetime(dt_obj)
        assert isinstance(dt_obj, DateTime)
        assert dt_obj.year == 2022
        assert dt_obj.month == 1
        assert dt_obj.day == 1
        assert dt_obj.hour == 0
        assert dt_obj.minute == 0

    @staticmethod
    def test_repr():
        dt_obj = DateTime(2022, 1, 1, 0, 0)
        assert repr(dt_obj) == "2021-W52-6 00:00"

    @staticmethod
    def test_str():
        dt_obj = DateTime(2022, 1, 1, 0, 0)
        assert str(dt_obj) == "2021-W52-6 00:00"


class TestTimeDelta:
    @staticmethod
    def test_from_slots():
        slots = 4
        td_obj = TimeDelta.from_slots(slots)
        assert td_obj.total_seconds() == slots * 15 * 60

    @staticmethod
    def test_from_timedelta():
        td = datetime.timedelta(days=1, seconds=3600)
        td_obj = TimeDelta.from_timedelta(td)
        assert td_obj.days == td.days
        assert td_obj.seconds == td.seconds

    @staticmethod
    def test_from_str():
        str_td = "1d-2h-3m-4w"
        td_obj = TimeDelta.from_str(str_td)
        assert td_obj.days == 1 + 4 * 7
        assert td_obj.seconds == 2 * 3600 + 3 * 60

    @staticmethod
    def test_to_str():
        td_obj = TimeDelta(days=1, seconds=3600)
        assert td_obj.to_str() == "1 day, 1:00:00"

    @staticmethod
    def test_repr():
        td_obj = TimeDelta(days=1, seconds=3600)
        assert repr(td_obj) == "1 day, 1:00:00"

    @staticmethod
    def test_to_slots():
        td_obj = TimeDelta(minutes=60)
        assert td_obj.to_slots() == 4


class TestTimeInterval:
    @staticmethod
    def test_init():
        start = DateTime(2022, 1, 1, 0, 0)
        end = DateTime(2022, 1, 1, 1, 0)
        ti = TimeInterval(start, end)
        assert ti.start == start
        assert ti.end == end

    @staticmethod
    def test_repr():
        start = DateTime(2022, 1, 1, 0, 0)
        end = DateTime(2022, 1, 1, 1, 0)
        ti = TimeInterval(start, end)
        assert repr(ti) == f"{start} -> {end} ({end - start})"

    @staticmethod
    def test_from_str():
        start_str = "2022-W01-1 00:00"
        end_str = "2022-W01-1 01:00"
        ti = TimeInterval.from_str(f"{start_str} -> {end_str}")
        assert ti.start == DateTime.from_str(start_str)
        assert ti.end == DateTime.from_str(end_str)

    @staticmethod
    def test_to_str():
        start = DateTime(2022, 1, 1, 0, 0)
        end = DateTime(2022, 1, 1, 1, 0)
        ti = TimeInterval(start, end)
        assert ti.to_str() == f"{start.to_str()} {end.to_str()}"

    @staticmethod
    def test_duration():
        start = DateTime(2022, 1, 1, 0, 0)
        end = DateTime(2022, 1, 1, 1, 0)
        ti = TimeInterval(start, end)
        assert ti.duration() == TimeDelta.from_timedelta(end - start)
