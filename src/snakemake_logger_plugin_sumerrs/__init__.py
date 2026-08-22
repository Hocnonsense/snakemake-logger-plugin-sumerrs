import logging
import sys
import threading
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional

from snakemake_interface_logger_plugins.base import LogHandlerBase
from snakemake_interface_logger_plugins.common import LogEvent
from snakemake_interface_logger_plugins.settings import LogHandlerSettingsBase


@dataclass
class LogHandlerSettings(LogHandlerSettingsBase):
    disable: Optional[str] = field(
        default="error",
        metadata={
            "help": "disable collecting and printing of warnings/errors/job_fail "
            "when snakemake workflow ends. comma-separated; errors are disabled "
            "by default (job failures and warnings are reported). "
            "Pass an empty string to report errors too",
            "type": str,
        },
    )
    out: Optional[str] = field(
        default="&2",
        metadata={
            "help": "output stream for printing errors and warnings when snakemake workflow ends. "
            "default (&2) is stderr, &1 for stdout, or a file path to append at the end",
            "type": str,
        },
    )


class ReportKind(StrEnum):
    WARNING = "warning"
    ERROR = "error"
    JOB_FAIL = "job_fail"

    @classmethod
    def all(cls):
        return set(cls)

    @classmethod
    def parse(cls, disable: Optional[str]):
        kinds = cls.all()
        if not disable:
            return kinds
        for token in disable.split(","):
            token = token.strip().lower()
            try:
                kinds.remove(cls(token))
            except ValueError:
                continue
        return kinds


class LogHandler(LogHandlerBase):
    def __post_init__(self):
        # LogHandlerSettings instance:
        self.settings: LogHandlerSettings
        self._collect = ReportKind.parse(self.settings.disable)
        self._out = str(self.settings.out)
        self._lock = threading.Lock()
        self._reported = False
        self._errors = []
        self._job_fail = []
        self._warnings = []

    def emit(self, record: logging.LogRecord):
        try:
            if not self._collect:
                return
            event = getattr(record, "event", None)
            if event in (LogEvent.JOB_ERROR, LogEvent.GROUP_ERROR):
                if ReportKind.JOB_FAIL in self._collect:
                    with self._lock:
                        self._job_fail.append(self.format(record))
            elif event == LogEvent.ERROR or record.levelno >= logging.ERROR:
                if ReportKind.ERROR in self._collect:
                    with self._lock:
                        self._errors.append(self.format(record))
            elif record.levelno >= logging.WARNING:
                if ReportKind.WARNING in self._collect:
                    with self._lock:
                        self._warnings.append(self.format(record))
        except Exception:
            self.handleError(record)

    def close(self):
        try:
            if not self._collect:
                return
            with self._lock:
                # Report exactly once. logging.shutdown() also closes every handler
                # at process exit, so without this guard the summary would print
                # a second (empty) time.
                if self._reported:
                    return
                self._reported = True
                errors = self._errors
                warnings = self._warnings
                job_fail = self._job_fail

            output = ["", "Snakemake ends with "]
            summaries = []

            def _sum(logs, logname: str):
                if not logs:
                    summaries.append(f"0 {logname}")
                    return
                # remove duplicates while preserving order
                _logs = list(dict.fromkeys(logs))
                n_logs = len(_logs)
                output.append("")
                if n_logs == 1:
                    summaries.append(f"1 {logname}")
                    output.append(f"{logname.capitalize()}:")
                else:
                    summaries.append(f"{len(_logs)} {logname}s")
                    output.append(f"{logname.capitalize()}s:")
                output.append(_logs[0])
                for item in _logs[1:]:
                    output.extend(["", item])

            if ReportKind.JOB_FAIL in self._collect:
                _sum(job_fail, "failed job")
            if ReportKind.ERROR in self._collect:
                _sum(errors, "error")
            if ReportKind.WARNING in self._collect:
                _sum(warnings, "warning")

            if len(summaries) == 1:
                output[1] += summaries[0]
            elif len(summaries) == 2:
                output[1] += f"{summaries[0]} and {summaries[1]}"
            else:
                output[1] += ", ".join(summaries[:-1]) + f", and {summaries[-1]}"

            if self._out == "&1":
                print("\n".join(output), file=sys.stdout)
            elif self._out == "&2":
                print("\n".join(output), file=sys.stderr)
            else:
                with open(self._out, "a+") as f:
                    print("\n".join(output), file=f)
        finally:
            super().close()

    @property
    def writes_to_stream(self):
        return False

    @property
    def writes_to_file(self):
        return False

    @property
    def has_filter(self):
        """independent of --quiet"""
        return True

    @property
    def has_formatter(self):
        return False

    @property
    def needs_rulegraph(self):
        return False
