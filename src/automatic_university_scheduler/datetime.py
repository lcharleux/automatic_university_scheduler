import datetime


class MetaTime:
    __add__ = lambda self, value: self._propagate_type(
        self._main_parent.__add__(self, value)
    )
    __mul__ = lambda self, value: self._propagate_type(super().__mul__(value))
    __sub__ = lambda self, value: self._propagate_type(super().__sub__(value))
    __neg__ = lambda self: self._propagate_type(super().__neg__())

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

    def to_slots(self) -> int:
        """
        Convert a TimeDelta object to 15min slots.
        """
        return int(self.total_seconds() // 900)


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
