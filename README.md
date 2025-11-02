# secret-santa

A web application for organizing Secret Santa gift exchanges with login authentication and persistent storage, built with Streamlit.

## Features

- **User Authentication**: Secure login system with usernames and passwords stored in configuration file
- **Persistent Storage**: Assignments are automatically generated on startup and stored in a database
- **Budget Display**: Shows the gift budget from the configuration file
- **Wish Lists**: Users can create and manage their wish lists
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

2. **Configure participants**
   
   Edit `config.yaml` to add your participants with usernames and passwords:
   ```yaml
   budget: 50
   participants:
     - username: alice
       password: aB3kL9mP
       name: Alice Johnson
   ```

3. **Install dependencies with Poetry**
   ```bash
   poetry install
   ```

4. **Run the application**
   ```bash
   poetry run streamlit run app.py
   ```

5. **Open your browser**
   Navigate to `http://localhost:8501` and login with any username/password from `config.yaml`

### Docker Deployment

#### Using Docker Compose (Recommended)

1. **Build and run the container**
   ```bash
   docker-compose up -d
   ```

2. **Stop the container**
   ```bash
   docker-compose down
   ```

#### Using Docker directly

1. **Build the Docker image**
   ```bash
   docker build -t secret-santa .
   ```

2. **Run the container**
   ```bash
   docker run -p 8501:8501 secret-santa
   ```

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
│   └── devcontainer.json    # Dev container configuration
├── app.py                    # Main Streamlit application
├── config.yaml              # Participants configuration (usernames, passwords, budget)
├── secret_santa.db          # TinyDB database (auto-generated, stores assignments & wishes)
├── pyproject.toml           # Poetry dependencies and project metadata
├── poetry.lock              # Locked dependency versions
├── Dockerfile               # Docker image definition
├── docker-compose.yml       # Docker Compose configuration
├── .gitignore              # Git ignore rules
└── README.md               # This file
```

## How to Use the Application

1. **Initial Setup**: 
   - Configure participants in `config.yaml` with usernames, passwords, and names
   - Set the gift budget
   - On first run, the app automatically generates Secret Santa assignments

2. **Login**: Each participant logs in with their username and password

3. **View Assignment**: After login, users see:
   - The gift budget
   - Who they are Secret Santa for
   - Their recipient's wish list (if any)

4. **Manage Wish List**: Users can:
   - Add items they'd like to receive
   - Remove items from their wish list
   - View what their Secret Santa will see

5. **Persistence**: Assignments are stored in `secret_santa.db` and persist across app restarts

## Development

### Adding Dependencies

```bash
poetry add <package-name>
```

### Running Tests

```bash
poetry run pytest
```

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
