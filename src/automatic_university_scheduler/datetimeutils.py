import datetime
import math


class MetaTime:
    __add__ = lambda self, value: self._propagate_type(
        self._main_parent.__add__(self, value)
    )
    __mul__ = lambda self, value: self._propagate_type(super().__mul__(value))
    __sub__ = lambda self, value: self._propagate_type(super().__sub__(value))
    __neg__ = lambda self: self._propagate_type(super().__neg__())
    __truediv__ = lambda self, value: self._propagate_type(super().__truediv__(value))
    __rsub__ = lambda self, value: self._propagate_type(super().__rsub__(value))

    @classmethod
    def _propagate_type(cls, out):
        """
        Propagate the type of the object to the output.
        """
        if out.__class__ == datetime.timedelta:
            return TimeDelta.from_timedelta(out)
        elif out.__class__ == datetime.datetime:
            return DateTime.from_str(out.to_str())
        else:
            return out


class DateTime(MetaTime, datetime.datetime):
    """
    Subclass of datetime.datetime with additional methods.
    """

    _main_parent = datetime.datetime

    @classmethod
    def from_str(cls, date_str: str) -> "DateTime":
        """
        Create a DateTime object from a string.
        """
        if "W" in date_str:
            return cls.strptime(date_str, "%G-W%V-%u %H:%M")
        else:
            return cls.strptime(date_str, "%d/%m/%Y %H:%M")

    def to_str(self, format="isocalendar") -> str:
        """
        Convert a DateTime object to a string.
        """
        if format == "isocalendar":
            return self.strftime("%G-W%V-%u %H:%M")
        elif format == "dmy":
            return self.strftime("%d/%m/%Y %H:%M")

    def __repr__(self) -> str:
        return self.to_str()

    def __str__(self) -> str:
        return self.to_str()

    @classmethod
    def from_datetime(cls, datetime: datetime.datetime) -> "DateTime":
        """
        Create a DateTime object from a datetime.
        """
        return cls(
            datetime.year, datetime.month, datetime.day, datetime.hour, datetime.minute
        )

    def __repr__(self) -> str:
        return f"{self.to_str()}"


class TimeDelta(MetaTime, datetime.timedelta):
    """
    Subclass of datetime.timedelta with additional methods.
    """

    _main_parent = datetime.timedelta

    @classmethod
    def from_slots(cls, slots: int) -> "TimeDelta":
        """
        Create a TimeDelta object from 15min slots.
        """
        return cls(minutes=slots * 15)

    @classmethod
    def from_timedelta(cls, timedelta: datetime.timedelta) -> "TimeDelta":
        """
        Create a TimeDelta object from a timedelta.
        """
        return cls(days=timedelta.days, seconds=timedelta.seconds)

    @classmethod
    def from_str(cls, str_timelta) -> "TimeDelta":
        """
        Create a TimeDelta object from a string.
        """
        w = str_timelta.split("-")
        out = {"days": 0, "hours": 0, "minutes": 0, "weeks": 0}
        dic = {"d": "days", "h": "hours", "m": "minutes", "w": "weeks"}
        for i in w:
            out[dic[i[-1]]] = int(i[:-1])
        return cls(**out)

    def to_str(self) -> str:
        """
        Convert a TimeDelta object to a string.
        """
        return str(self)

    def __repr__(self) -> str:
        return f"{self.to_str()}"

    def to_slots(self, slot_duration=None) -> int:
        """
        Convert a TimeDelta object to slots. Default: 15min slots.
        """
        if slot_duration is None:
            slot_duration = TimeDelta(minutes=15)
        return self.total_seconds() // slot_duration.total_seconds()


class TimeInterval:
    def __init__(self, start: DateTime, end: DateTime):
        self.start = start
        self.end = end

    def __repr__(self) -> str:
        return f"{self.start} -> {self.end} ({self.duration()})"

    @classmethod
    def from_str(cls, s: str, sep: str = " -> ") -> "TimeInterval":
        start, end = s.split(sep)
        return cls(DateTime.from_str(start), DateTime.from_str(end))

    def to_str(self) -> str:
        return f"{self.start.to_str()} {self.end.to_str()}"

    def duration(self) -> TimeDelta:
        return self.end - self.start

    def to_slots(
        self,
        origin_datetime: DateTime,
        horizon_datetime: DateTime,
        slot_duration: TimeDelta,
    ) -> tuple[int, int]:
        """
        Convert a TimeInterval object to 15min slots.
        """
        start = min(max(self.start, origin_datetime), horizon_datetime)
        end = min(max(self.end, origin_datetime), horizon_datetime)
        if start == end:  # If the interval is empty
            return None
        else:  # If the interval is not empty
            start_slot = math.floor(
                (start - origin_datetime).to_slots(slot_duration=slot_duration)
            )
            end_slot = math.ceil(
                (end - origin_datetime).to_slots(slot_duration=slot_duration)
            )
            return start_slot, end_slot


def read_time_intervals(
    start: str, end: str, repeat: int = 1, offset: str = "1w"
) -> list[TimeInterval]:
    """
    Read time intervals from a dictionary.
    """
    start = DateTime.from_str(start)
    end = DateTime.from_str(end)
    offset = TimeDelta.from_str(offset)
    time_intervals = [
        TimeInterval(start + i * offset, end + i * offset) for i in range(repeat)
    ]
    return time_intervals


def datetime_to_slot(
    datetime: DateTime, origin_datetime: DateTime, slot_duration: TimeDelta, round=None
) -> int:
    """
    Convert a DateTime object to a 15min slot.
    """
    slot = (datetime - origin_datetime).to_slots(slot_duration=slot_duration)
    if round == "ceil":
        return math.ceil(slot)
    elif round == "floor":
        return math.floor(slot)
    return slot


def slot_to_datetime(slot, origin_datetime, time_slot_duration):
    """
    Converts a slot to a datetime.
    """
    return origin_datetime + slot * time_slot_duration
