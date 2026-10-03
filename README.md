# Secret Santa Web Application (Vibe Coded)

A multilingual web app to organize Secret Santa gift exchanges for several families or friend groups at once. Built with Streamlit, stored in a small JSON database, and shipped as a Docker container.

## Features

- **Admin console**: an admin account, created on the first start, manages groups and people, generates and shares their passwords, runs the draws and follows who still has to add their wishes
- **Hidden results**: nobody sees the result of a draw, not even the admin, who can reveal it only if something needs checking
- **Multiple groups**: one deployment serves several families or friend groups, each with its own budget, currency, draw and wish lists
- **One login per person**: people in several groups (e.g. their own family and their partner's family) switch between their groups on their personal page
- **Separate wish lists per group**: each Secret Santa only sees the wish list written for their group
- **Exclusion rules**: partners (or anyone else) never draw each other, in every group they share
- **Wish lists with links**: people add what they'd like to receive, including links to online shops
- **Multi-language**: English, German and Italian, switchable at any time
- **Reset with backup**: start a new round for next year, or reset everything; a backup of the database is saved first

## Quick Start (Docker)

```bash
git clone https://github.com/massimilianobotticelli/vibed-santa.git
cd vibed-santa
docker compose up -d
```

Open `http://localhost:8501` and:

1. **Create the admin account** (the app asks for it on the first start)
2. **People**: add everyone taking part. The username is created from the name and a password is generated, unless you type them. Set who doesn't exchange gifts with whom (e.g. partners)
3. **Groups**: create the groups with their budget, currency and participants. A person can be in several groups with the same login
4. **Share the logins**: each person has a ready-to-copy box with their username and password; *Show all logins* lists everyone at once
5. **Draws**: once everyone is in, run the draw of each group. Participants can log in and fill their wish lists before and after the draw

All data is stored in `data/secret_santa.db`, which is mounted as a volume and persists across restarts and rebuilds.

```bash
docker compose logs -f   # view logs
docker compose down      # stop
```

## Using the App

### Participants

Participants log in on the *Participant* tab with their username and password and see:

- the gift budget of their group
- who they are Secret Santa for, and that person's wish list (once the draw has run)
- their own wish list, to add and remove items
- if they are in several groups, a switcher at the top of the page to move between them

### Admin Console

The admin logs in on the *Admin* tab. The console has four sections:

- **Draws**: for each group, run the draw (results stay hidden), see who has not added any wishes yet, reveal the results with *Show results (spoiler!)* if needed, and redo the draw. A warning appears when participants were added or removed after the draw
- **Groups**: create, edit and delete groups (name, budget, currency, participants). Deleting a group also deletes its draw and wish lists
- **People**: add, edit and delete people, set exclusions and groups, see their login details and generate new passwords
- **Reset**:
  - *Start a new round* deletes all draws and wish lists (e.g. for next year) and keeps groups, people and logins
  - *Reset everything* deletes all data, including the admin account, after confirming with the admin password

  Before every reset, a backup is saved as `data/secret_santa.<timestamp>.bak.db`. To undo a reset, stop the app and copy the backup over `data/secret_santa.db`.

### Exclusion Rules

"Doesn't exchange gifts with" on a person works in both directions and applies in every group both people are in. Typical uses are couples and people living together.

## Deployment

The app listens on port `8501`. For a deployment reachable from the internet:

- **Put it behind a reverse proxy with HTTPS** (e.g. Nginx Proxy Manager, Caddy, Traefik). Streamlit uses WebSockets, so the proxy must forward them (`Upgrade` / `Connection` headers)
- **Create the admin account right after the first start**: until it exists, whoever opens the app can create it
- **Back up the `data/` directory**: it contains the whole database

### Upgrading from an Older Version

Older versions read groups and people from `.appconfig.yaml`. To move an existing deployment to this version:

1. Keep the existing `data/secret_santa.db`
2. Copy the old `.appconfig.yaml` to `data/appconfig.yaml`
3. Start the new version and create the admin account

On the first start the configuration is imported (only into a database without groups and people, then the file is renamed to `data/appconfig.yaml.imported`), the old draws are converted and the old wish lists are assigned to the groups of each person. Use *Reset → Start a new round* to clear last year's draws and wish lists. See `.appconfig.template.yaml` for the format, which can also be used to create many groups at once.

### Security Notes

- People's passwords are stored in plain text in the database, so the admin can see and share them. Use generated passwords, not passwords people use elsewhere
- The admin password is stored as a salted PBKDF2 hash
- The `data/` directory and `.appconfig.yaml` are git-ignored; never commit them

## Development

### Local Development

Requires Python 3.11+ and Poetry:

```bash
poetry install
poetry run streamlit run app.py
```

A VS Code Dev Container configuration is also available (`Dev Containers: Reopen in Container`).

### Running Tests

Tests run in Docker via the `tests` service (only started on demand):

```bash
docker compose run --rm --build tests
```

Or locally with Poetry: `poetry run pytest`

### Project Structure

```
vibed-santa/
├── app.py                      # Streamlit application (pages and admin console)
├── admin.py                    # Admin account (hashed password)
├── groups.py                   # Groups and people, YAML import
├── draws.py                    # Secret Santa draws
├── wishes.py                   # Wish lists, one per person and group
├── reset.py                    # New round / reset everything, with backup
├── translations.yaml           # UI texts (EN, DE, IT)
├── tests/                      # Pytest test suite
├── .appconfig.template.yaml    # Example configuration to import (optional)
├── Dockerfile
├── docker-compose.yml          # App service, and the "tests" service
├── pyproject.toml / poetry.lock
└── data/                       # Created at runtime: database, backups (git-ignored)
```

### Database Structure

`data/secret_santa.db` is a [TinyDB](https://tinydb.readthedocs.io/) JSON file with the tables:

- **admin**: the admin account (`username`, `salt`, `password_hash`)
- **people**: `username`, `name`, `password`, `exclude` (usernames)
- **groups**: `id`, `name`, `budget`, `currency`, `members` (usernames)
- **draws**: one per group: `family_id`, `drawn_at`, `assignments` (giver → receiver)
- **wishes**: one per person and group: `family_id`, `username`, `items`

### Translations

All UI texts are in `translations.yaml`, one entry per text with a translation per language:

```yaml
translations:
  title:
    en: "🎅 Secret Santa"
    de: "🎅 Wichteln"
    it: "🎅 Babbo Natale Segreto"
```

To add a language, add its code to every entry and to `LANGUAGES` in `app.py`.

## License

MIT License - feel free to use this project for your Secret Santa events!

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
