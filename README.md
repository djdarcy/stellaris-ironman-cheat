# stellaris-ironman-cheat

A new project created from git-repokit-template

## Installation

```bash
pip install stellaris_ironman_cheat
```

### From Source

```bash
git clone https://github.com/djdarcy/stellaris-ironman-cheat.git
cd stellaris-ironman-cheat
pip install -e ".[dev]"
```

## Usage

```bash
stellaris-ironman-cheat --help
```

## Development

```bash
# Clone and install
git clone https://github.com/djdarcy/stellaris-ironman-cheat.git
cd stellaris-ironman-cheat
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -v

# Install git hooks (if using repokit-common submodule)
bash scripts/repokit-common/install-hooks.sh
```

## License

GPL-3.0-or-later. See [LICENSE](LICENSE) for details.

