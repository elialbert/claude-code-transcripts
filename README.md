# claude-code-publish

[![PyPI](https://img.shields.io/pypi/v/claude-code-publish.svg)](https://pypi.org/project/claude-code-publish/)
[![Changelog](https://img.shields.io/github/v/release/simonw/claude-code-publish?include_prereleases&label=changelog)](https://github.com/simonw/claude-code-publish/releases)
[![Tests](https://github.com/simonw/claude-code-publish/workflows/Test/badge.svg)](https://github.com/simonw/claude-code-publish/actions?query=workflow%3ATest)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/simonw/claude-code-publish/blob/main/LICENSE)

Convert Claude Code `session.json` files to clean, mobile-friendly HTML pages with pagination.

[Example transcript](https://static.simonwillison.net/static/2025/claude-code-microjs/index.html) produced using this tool.


## Installation

Install this tool using `uv`:
```bash
uv tool install claude-code-publish
```
Or run it without installing:
```bash
uvx claude-code-publish --help
```

## Usage

When using [Claude Code for web](https://claude.ai/code) you can export your session as a `session.json` file using the `teleport` command (and then hunting around on disk).

This tool converts that JSON into a browseable multi-page HTML transcript.

```bash
claude-code-publish session.json -o output-directory/
```

This will generate:
- `index.html` - an index page with a timeline of prompts and commits
- `page-001.html`, `page-002.html`, etc. - paginated transcript pages

### Options

- `-o, --output DIRECTORY` - output directory (default: current directory)
- `--repo OWNER/NAME` - GitHub repo for commit links (auto-detected from git push output if not specified)

## Development

To contribute to this tool, first checkout the code. You can run the tests using `uv run`:
```bash
cd claude-code-publish
uv run pytest
```
And run your local development copy of the tool like this:
```bash
uv run claude-code-publish --help
```
