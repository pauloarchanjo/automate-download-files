# ADF — Automate Download Files

A lightweight CLI utility that automatically keeps your Downloads directory organized.

ADF watches a directory, classifies files by configurable extension rules, and moves them into predictable destinations without silently overwriting existing files.

## Why ADF

The project began as a small `watchdog` script and was refactored into a focused command-line application with clear separation between configuration, classification, organization, filesystem events, and terminal presentation.

Core principles:

- simple and predictable behavior;
- low resource usage while watching;
- safe duplicate handling;
- protection against incomplete downloads;
- cross-platform paths;
- clean CLI identity;
- testable business logic.

## Requirements

- Python 3.11+
- Windows, Linux, or macOS

## Installation

Clone the project and install it in a virtual environment:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e .
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -e .
```

After installation:

```bash
adf
adf --help
```

## First setup

Create the default configuration:

```bash
adf init
```

ADF stores configuration in the platform-appropriate user configuration directory. You can inspect the exact path with:

```bash
adf config path
```

## Commands

```bash
adf
adf --help
adf init
adf organize --dry-run
adf organize
adf watch
adf status
adf rules
adf doctor
adf version
```

### Watch continuously

```bash
adf watch
```

Use another directory:

```bash
adf watch --directory ~/Downloads
```

Preview watcher actions without moving files:

```bash
adf watch --dry-run
```

### Organize immediately

```bash
adf organize
```

Always preview first when testing a new configuration:

```bash
adf organize --dry-run
```

### Inspect rules

```bash
adf rules
adf rules --category images
```

### Diagnose the environment

```bash
adf doctor
```

The doctor checks the configured directory, read/write access, configuration, loaded rules, core dependencies, and basic watchdog initialization.

## Configuration

ADF uses TOML. A generated configuration resembles:

```toml
[general]
directory = "~/Downloads"
create_directories = true
handle_duplicates = "rename"
unknown_destination = "Others"

[categories.images]
destination = "Images"
extensions = [".jpg", ".jpeg", ".png", ".webp"]

[categories.pdf]
destination = "Documents/PDF"
extensions = [".pdf"]

[categories.archives]
destination = "Archives"
extensions = [".zip", ".rar", ".7z"]
```

Duplicate policies supported by the current configuration model are `rename`, `skip`, and `overwrite`. The safe default is `rename`.

Unknown extensions go to `Others/` by default.

Files ending in `.crdownload`, `.part`, `.tmp`, or `.download` are never moved. The watcher also waits for file size and modification time to stabilize before organizing a new file.

## Project structure

```text
adf_project/
├── pyproject.toml
├── README.md
├── src/
│   └── adf/
│       ├── __init__.py
│       ├── classifier.py
│       ├── cli.py
│       ├── config.py
│       ├── downloads.py
│       ├── exceptions.py
│       ├── models.py
│       ├── organizer.py
│       ├── watcher.py
│       └── presentation/
│           ├── __init__.py
│           └── console.py
└── tests/
    ├── test_classifier.py
    ├── test_config.py
    └── test_organizer.py
```

## Architecture

The watcher only detects relevant filesystem events. `FileOrganizer` owns the use-case flow, `FileClassifier` resolves extension rules, configuration is isolated in `config.py`, and Rich-specific rendering stays inside the presentation layer.

```text
Filesystem event
      ↓
DownloadWatcher
      ↓
FileOrganizer
      ↓
FileClassifier
      ↓
Duplicate resolution
      ↓
Filesystem move
```

This is intentionally smaller than a full DDD architecture. The project uses explicit models and boundaries where they improve clarity and tests, without repository or service interfaces that would add ceremony without value.

## Development

Install development dependencies:

```bash
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

Run linting:

```bash
ruff check .
```

## Safety behavior

ADF does not move directories, does not silently overwrite files under the default policy, skips incomplete download extensions, ignores filesystem events outside the configured root, and continues watching after individual file-processing failures.

## Future ideas

Possible future additions, intentionally not implemented in the current version:

- undo and move history;
- desktop notifications;
- MIME-type rules;
- date-based organization;
- startup integration;
- background service mode;
- system tray integration.
