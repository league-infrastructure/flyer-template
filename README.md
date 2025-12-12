# flyer-template

This repo is an installable Python application (not just a single script).

- Importable application/library code lives in `src/flyte/`.
- The `flyte` command is installed via a console-script entrypoint.

## Try it locally (pip)

```zsh
python -m pip install -e .
flyte
```

## Install with pipx

From this repo root:

```zsh
pipx install .
flyte
```

## Layout

- `src/flyte/hello.py` contains `hello_world()`
- `src/flyte/cli.py` contains `main()` (entrypoint)
- `main.py` is just a thin wrapper that calls `flyte.cli:main`
