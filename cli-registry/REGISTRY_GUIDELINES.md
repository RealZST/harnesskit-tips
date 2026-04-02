# CLI Registry Guidelines

This file describes how to add or update entries in `registry.json`.

## Entry Schema

Each entry in the JSON array has the following fields:

| Field | Type | Required | Description |
|---|---|---|---|
| `binary_name` | string | yes | The executable name users type on the command line (e.g. `wecom-cli`). Must be unique across all entries. |
| `display_name` | string | yes | Human-readable name shown in the marketplace UI. |
| `description` | string | yes | One-line summary of what the CLI does. Use an em-dash (`—`) to separate the tool name from its capabilities. |
| `install_command` | string | yes | Shell command to install the CLI binary (npm, pip, curl, go install, etc.). |
| `skills_repo` | string | yes | GitHub `owner/repo` path where the CLI's skill definitions live. |
| `skills_install_command` | string or null | yes | If the CLI requires a separate step to install skills, provide the command here; otherwise `null`. |
| `icon_url` | string or null | yes | URL to a square icon (recommended 128x128 PNG). Set to `null` if no icon is available yet. |
| `categories` | string[] | yes | One or more category tags for filtering. Use lowercase kebab-case (e.g. `"browser-automation"`). |
| `verified` | boolean | yes | Whether the entry has been reviewed and approved by maintainers (see below). |
| `api_domains` | string[] | yes | Domains the CLI communicates with. Used for firewall/proxy hints. Empty array if none. |
| `credentials_path` | string or null | yes | Default filesystem path where the CLI stores credentials. Use `~` for the home directory. `null` if the CLI does not persist credentials. |

## What "verified" means

A CLI entry is marked `"verified": true` when **all** of the following are satisfied:

1. The `skills_repo` exists and contains valid skill definitions.
2. The `install_command` has been tested and installs a working binary.
3. A maintainer has reviewed the entry for accuracy and security (no suspicious install scripts, no exfiltration of credentials, etc.).

Community-submitted entries start as `"verified": false` and are promoted after review.

## Adding a new entry

1. Append a new object to the array in `registry.json`.
2. Fill in every field — use `null` or `[]` for optional/empty values, never omit a field.
3. Set `"verified": false` unless you are a maintainer performing a verified addition.
4. Open a pull request with a brief explanation of what the CLI does and why it belongs in the registry.
