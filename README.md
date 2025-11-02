# Secret Santa Web Application

A multilingual web application for organizing Secret Santa gift exchanges with multiple groups, login authentication, and persistent storage. Built with Streamlit.

## Features

- **Multi-Language Support**: Interface available in English, German, and Italian with user-selectable language
- **Multiple Groups**: Support for multiple families or friend groups in a single deployment
- **User Authentication**: Secure login system with usernames and passwords
- **Persistent Storage**: Assignments are automatically generated and stored in a database
- **Exclusion Rules**: Configure who cannot be assigned to whom (e.g., couples)
- **Budget Display**: Shows the gift budget for each group
- **Wish Lists**: Users can create and manage their wish lists with support for links (Amazon, online shops, etc.)
- **Private Assignment View**: Each user can only see their own Secret Santa assignment and their recipient's wish list
- **Auto-generation**: Assignments are created once and persist across app restarts

## Technologies

- **Streamlit**: Web application framework
- **Poetry**: Dependency management
- **TinyDB**: Lightweight JSON database for storing assignments and wish lists
- **PyYAML**: Configuration file parsing
- **Docker**: Containerization
- **Dev Container**: Development environment

## Getting Started

### Prerequisites

- Python 3.11+
- Poetry (for local development)
- Docker (for containerized deployment)
- VS Code with Dev Containers extension (optional, for devcontainer)

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/massimilianobotticelli/secret-santa.git
   cd secret-santa
   ```

2. **Configure groups and participants**
   
   Edit `.appconfig.yaml` to add your groups with participants, usernames, passwords, and exclusion rules:
   ```yaml
   families:
     - id: my_family
       name: Smith Family
       budget: 50
       currency: "$"  # Currency symbol
       participants:
         - username: alice
           password: secure123
           name: Alice Smith
           exclude: [bob]  # Alice cannot be assigned to Bob
         
         - username: bob
           password: pass456
           name: Bob Smith
           exclude: [alice]  # Bob cannot be assigned to Alice
   ```

3. **Configure translations (optional)**
   
   The `translations.yaml` file contains all UI text in English, German, and Italian. You can add more languages or modify existing translations.

4. **Install dependencies with Poetry**
   ```bash
   poetry install
   ```

5. **Run the application**
   ```bash
   poetry run streamlit run app.py
   ```

6. **Open your browser**
   Navigate to `http://localhost:8501`, select your language and group, then login with any username/password from `.appconfig.yaml`

### Docker Deployment

#### Using Docker Compose (Recommended)

1. **Create your configuration file**
   ```bash
   cp .appconfig.template.yaml .appconfig.yaml
   # Edit .appconfig.yaml with your groups and participants
   ```

2. **Build and run the container**
   ```bash
   docker-compose up -d
   ```
   
   The configuration files are mounted as volumes, so you can edit them without rebuilding:
   - `.appconfig.yaml` - Edit groups and participants
   - `translations.yaml` - Edit translations (optional)
   - `data/` - Directory containing `secret_santa.db` (persists between restarts)

3. **Edit configuration while running**
   
   You can modify `.appconfig.yaml` on your host machine at any time. The app will use the updated configuration on the next page refresh or restart:
   ```bash
   # Edit the config file
   nano .appconfig.yaml
   
   # Restart the container to apply changes
   docker-compose restart
   ```

4. **View logs**
   ```bash
   docker-compose logs -f
   ```

5. **Stop the container**
   ```bash
   docker-compose down
   ```

#### Using Docker directly

1. **Build the Docker image**
   ```bash
   docker build -t secret-santa .
   ```

2. **Run the container with mounted config**
   ```bash
   docker run -p 8501:8501 \
     -v $(pwd)/.appconfig.yaml:/app/.appconfig.yaml \
     -v $(pwd)/data:/app/data \
     -v $(pwd)/translations.yaml:/app/translations.yaml \
     secret-santa
   ```
   
   The `-v` flags mount local files/directories into the container:
   - `.appconfig.yaml` - Configuration file (editable)
   - `data/` - Directory for database persistence
   - `translations.yaml` - Translations (editable)

3. **Access the application**
   Open `http://localhost:8501` in your browser

### Development with VS Code Dev Container

1. **Open the project in VS Code**
   ```bash
   code .
   ```

2. **Reopen in Container**
   - Press `F1` or `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
   - Select `Dev Containers: Reopen in Container`
   - Wait for the container to build and start

3. **Run the application**
   The application will be available at `http://localhost:8501`

## Project Structure

```
secret-santa/
├── .devcontainer/
│   └── devcontainer.json      # Dev container configuration
├── app.py                      # Main Streamlit application
├── .appconfig.yaml            # Groups and participants configuration
├── translations.yaml          # Multi-language translations (EN, DE, IT)
├── secret_santa.db            # TinyDB database (auto-generated, stores assignments & wishes)
├── pyproject.toml             # Poetry dependencies and project metadata
├── poetry.lock                # Locked dependency versions
├── Dockerfile                 # Docker image definition
├── docker-compose.yml         # Docker Compose configuration
├── .gitignore                 # Git ignore rules
└── README.md                  # This file
```

## How to Use the Application

1. **Initial Setup**: 
   - Configure groups (families or friend groups) in `.appconfig.yaml` with:
     - Group ID, name, budget, and currency
     - Participants with usernames, passwords, and names
     - Exclusion rules (who cannot be assigned to whom)
   - On first run, the app automatically generates Secret Santa assignments per group

2. **Select Language**: Choose between English, German, or Italian using the language selector (EN | DE | IT)

3. **Select Group**: Choose your family or friend group from the dropdown

4. **Login**: Enter your username and password

5. **View Assignment**: After login, users see:
   - The gift budget for their group (in the configured currency)
   - Who they are Secret Santa for
   - Their recipient's wish list (if any)
   - Language switcher in the sidebar

6. **Manage Wish List**: Users can:
   - Add items they'd like to receive (including links to Amazon, online shops, etc.)
   - Remove items from their wish list
   - View what their Secret Santa will see

7. **Persistence**: Assignments and wish lists are stored in `data/secret_santa.db` and persist across app restarts

8. **Managing Groups**: 
   - **Adding New Groups**: You can add new families/groups to `.appconfig.yaml` at any time
     - The app will automatically generate assignments for new groups on next startup
   - **Removing Groups**: If you remove a group from `.appconfig.yaml`
     - The group's assignments are automatically deleted from the database on next startup
     - This keeps the database clean and in sync with your configuration
   - **Important**: Existing group assignments are NEVER modified - they remain unchanged
   - To reset assignments for an existing group, delete the database file or remove and re-add the group

## Configuration

### Group Configuration (`.appconfig.yaml`)

```yaml
families:
  - id: group_identifier          # Unique ID for the group
    name: Display Name            # Name shown in the UI
    budget: 50                    # Gift budget amount
    currency: "$"                 # Currency symbol ($, €, £, ¥, etc.)
    participants:
      - username: user1           # Login username
        password: pass1           # Login password
        name: Display Name 1      # Full name shown in app
        exclude: [user2]          # Optional: users they cannot be assigned to
      
      - username: user2
        password: pass2
        name: Display Name 2
        exclude: [user1]
```

### Translations (`translations.yaml`)

The translations file uses a key-first structure for easy maintenance:

```yaml
translations:
  key_name:
    en: "English translation"
    de: "German translation"
    it: "Italian translation"
```

All UI text is translatable. To add a new language, add a new language code to each translation key.

## Development

### Adding Dependencies

```bash
poetry add <package-name>
```

### Running Tests

```bash
poetry run pytest
```

### Adding a New Language

1. Open `translations.yaml`
2. Add your language code (e.g., `fr` for French) to each translation key:
   ```yaml
   title:
     en: "🎅 Secret Santa"
     de: "🎅 Wichteln"
     it: "🎅 Babbo Natale Segreto"
     fr: "🎅 Père Noël Secret"  # New language
   ```
3. Update the language selector buttons in `app.py` to include your new language

### Database Structure

The `secret_santa.db` file contains:
- **assignments_[group_id]**: Tables for each group's Secret Santa assignments
- **wishes**: Table storing wish lists for all users

## Key Features Explained

### Exclusion Rules

Exclusion rules prevent certain people from being assigned to each other. This is useful for:
- Couples who shouldn't be assigned to each other
- People who live together
- Any other pairs where gift-giving would be awkward

Example:
```yaml
participants:
  - username: alice
    name: Alice
    exclude: [bob, charlie]  # Alice won't be assigned to Bob or Charlie
```

### Multi-Group Support

Each group operates independently:
- Separate Secret Santa assignments
- Separate budgets
- Separate participant lists
- Wish lists are shared (visible across groups if someone participates in multiple)

### Language Selection

- Users can change language at any time (login page and sidebar)
- Language preference is stored in session state
- All text updates immediately when language is changed

## Dockerfile Details

The Dockerfile includes all the important steps to run the application:

1. **Base Image**: Uses Python 3.11 slim for a lightweight container
2. **Environment Variables**: Sets up Python and Poetry configuration
3. **System Dependencies**: Installs curl and build-essential for Poetry installation
4. **Poetry Installation**: Installs Poetry for dependency management
5. **Dependency Installation**: Uses Poetry to install Python dependencies
6. **Application Copy**: Copies the Streamlit application code
7. **Port Exposure**: Exposes port 8501 for Streamlit
8. **Health Check**: Includes a health check endpoint
9. **CMD**: Runs the Streamlit application

## License

MIT License - feel free to use this project for your Secret Santa events!

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
