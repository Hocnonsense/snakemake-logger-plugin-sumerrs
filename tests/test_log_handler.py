import contextlib
import io
import logging
import unittest
from types import SimpleNamespace

from snakemake_interface_logger_plugins.common import LogEvent

from snakemake_logger_plugin_sumerrs import LogHandler, LogHandlerSettings

try:
    from snakemake.logging import DefaultFormatter

    HAS_DEFAULT_FORMATTER = True
except ImportError:
    HAS_DEFAULT_FORMATTER = False


def make_record(level, msg, event=None, **extra):
    record = logging.LogRecord(
        name="snakemake",
        level=level,
        pathname="",
        lineno=0,
        msg=msg,
        args=(),
        exc_info=None,
    )
    if event is not None:
        extra["event"] = event
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def make_handler(disable=None):
    # disable=None keeps the settings default ("error": errors not reported).
    settings = LogHandlerSettings()
    if disable is not None:
        settings.disable = disable
    common = SimpleNamespace(dryrun=False)
    handler = LogHandler(common, settings)
    if HAS_DEFAULT_FORMATTER:
        handler.setFormatter(DefaultFormatter())
    return handler


def run_close(handler):
    buffer = io.StringIO()
    with contextlib.redirect_stderr(buffer):
        handler.close()
    return buffer.getvalue()


def run_flush(handler):
    buffer = io.StringIO()
    with contextlib.redirect_stderr(buffer):
        handler.flush()
    return buffer.getvalue()


def job_error_record(rule="foo", msg="boom"):
    return make_record(
        logging.ERROR,
        "Error in rule foo, jobid: 0",
        event=LogEvent.JOB_ERROR,
        rule_name=rule,
        rule_msg=msg,
        jobid=0,
        input=["in.txt"],
        output=["out.txt"],
        log=["log/foo.log"],
        conda_env=None,
        shellcmd="echo boom",
        aux={},
    )


class TestLogHandler(unittest.TestCase):
    def test_job_fail_disabled(self):
        handler = make_handler(disable="job_fail")
        handler.emit(job_error_record())

        output = run_close(handler)

        self.assertNotIn("failed job", output)
        self.assertIn("0 error and 0 warning", output)

    def test_errors_reported_when_explicitly_enabled(self):
        handler = make_handler(disable="")
        handler.emit(make_record(logging.ERROR, "an error happened"))

        output = run_close(handler)

        self.assertIn("0 failed job, 1 error, and 0 warning", output)
        self.assertIn("Error:", output)
        self.assertIn("an error happened", output)

    def test_warning_reported_by_default(self):
        handler = make_handler()
        handler.emit(make_record(logging.WARNING, "a warning happened"))

        output = run_close(handler)

        self.assertIn("0 failed job and 1 warning", output)
        self.assertIn("Warning:", output)
        self.assertIn("a warning happened", output)

    def test_job_error_formatted_with_default_formatter(self):
        handler = make_handler()
        handler.emit(job_error_record())

        output = run_close(handler)

        self.assertIn("1 failed job and 0 warning", output)
        self.assertIn("Failed job:", output)
        self.assertIn("Error in rule foo", output)
        if HAS_DEFAULT_FORMATTER:
            self.assertIn("message: boom", output)
            self.assertIn("output: out.txt", output)
            self.assertIn("log: log/foo.log", output)
            self.assertIn("shell:", output)

    def test_outputs_zero_summary_when_no_records(self):
        handler = make_handler()

        output = run_close(handler)

        self.assertIn("0 failed job and 0 warning", output)

    def test_disabled_when_all_kinds_disabled(self):
        handler = make_handler(disable="warning,error,job_fail")
        handler.emit(job_error_record())

        self.assertEqual(run_close(handler), "")

    def test_unknown_disable_tokens_are_ignored(self):
        handler = make_handler(disable="bogus,warning")
        handler.emit(make_record(logging.WARNING, "a warning happened"))
        handler.emit(make_record(logging.ERROR, "an error happened"))

        output = run_close(handler)

        self.assertIn("0 failed job and 1 error", output)
        self.assertNotIn("warning", output)
        self.assertIn("Error:", output)
        self.assertNotIn("Warning:", output)

    def test_close_is_idempotent(self):
        handler = make_handler(disable="")
        handler.emit(make_record(logging.ERROR, "an error happened"))

        first = io.StringIO()
        with contextlib.redirect_stderr(first):
            handler.close()
        second = io.StringIO()
        with contextlib.redirect_stderr(second):
            handler.close()

        self.assertIn("1 error", first.getvalue())
        self.assertEqual(second.getvalue(), "")

    def test_flush_does_not_report(self):
        handler = make_handler(disable="")
        handler.emit(make_record(logging.ERROR, "an error happened"))

        self.assertEqual(run_flush(handler), "")

    def test_out_redirects_to_stdout(self):
        handler = make_handler(disable="")
        handler.settings.out = "&1"
        handler._out = "&1"
        handler.emit(make_record(logging.ERROR, "an error happened"))

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            handler.close()
        self.assertIn("an error happened", buffer.getvalue())

    def test_collects_and_prints_group_error(self):
        handler = make_handler()
        record = make_record(
            logging.ERROR,
            "Error in group 1",
            event=LogEvent.GROUP_ERROR,
            aux_logs=["log/group.log"],
            job_error_info=[
                {
                    "rule_name": "a",
                    "jobid": 0,
                    "output": ["a.out"],
                    "log": ["log/a.log"],
                },
                {"rule_name": "b", "jobid": 1, "output": [], "log": []},
            ],
        )
        handler.emit(record)

        output = run_close(handler)

        self.assertIn("1 failed job and 0 warning", output)
        self.assertIn("Failed job:", output)
        self.assertIn("Error in group 1", output)
        if HAS_DEFAULT_FORMATTER:
            self.assertIn("jobs:", output)
            self.assertIn("rule a:", output)
            self.assertIn("log: log/a.log", output)


if __name__ == "__main__":
    unittest.main()
