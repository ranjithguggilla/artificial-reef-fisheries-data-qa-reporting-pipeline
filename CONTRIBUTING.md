# Contributing

Thanks for helping improve this project.

## Local setup

1. Clone and enter the repository.
2. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

Or use:

```bash
make setup
```

## Run locally

```bash
make run
```

## Validate before opening a PR

Run the smoke test:

```bash
make smoke
```

## Commit hygiene

To avoid accidental co-author trailers that affect GitHub contributors, this repo includes a local commit message hook:

```bash
git config core.hooksPath .githooks
```

Run that command once per local clone.
