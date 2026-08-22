snakemake-logger-plugin-sumerrs
================================

A Snakemake logger plugin that collects warnings, plain errors and job failures during workflow runs, and reprints them when the run ends.
It is a third output channel, in addition to Snakemake's live screen output and its logfile.

## Usage

### Installation

```bash
pip install snakemake-logger-plugin-sumerrs
```

### Enable

Enable the plugin with `--logger`:

```bash
snakemake --logger sumerrs --cores 1
```

#### Example

```
Snakemake ends with 1 failed job and 0 warning

Failed job:
[Sat Aug 22 22:10:34 2026]
Error in rule fail:
    message: None
    jobid: 1
    output: out.txt
    shell:
        false
        (command exited with non-zero exit code)
```

## Settings

| Parameter                  | Value                                                                                                            | Description                                      |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| `--logger-sumerrs-disable` | `warning`, `error`, `job_fail`; unknown tokens are ignored. Default is `error`, pass `""` to also report errors. | Comma-separated list of report kinds to disable. |
| `--logger-sumerrs-out`     | `&2` (default) is stderr, `&1` is stdout, or a file path to append to.                                           | Where to print the report.                       |

```bash
# also report errors
snakemake --logger sumerrs --logger-sumerrs-disable ""

# write to stdout (quote it: `&` is a shell metacharacter)
snakemake --logger sumerrs --logger-sumerrs-out '&1'

# append to a file
snakemake --logger sumerrs --logger-sumerrs-out error.log
```

## Behavior

- The plugin stays quiet during the run: it only collects records and prints the report once, when the run ends.
- It is printed directly to the chosen stream and never goes through Snakemake's logging handlers again, so it does not appear in the logfile.
- It is independent of `--quiet`.
- The report is emitted from `close()`, i.e. after the logger queue has been drained by `LoggerManager.stop()`.
- Job-failure entries are rendered with Snakemake's `DefaultFormatter`, so they look exactly like the console output (including `--print-logfiles`).
- The plugin handler is active only in the main process (`ExecMode.DEFAULT`); subprocess/remote job processes skip plugin handlers.

## Development

```bash
pixi install
pixi run test
# or
pixi run -e test pytest
```
