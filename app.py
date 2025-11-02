import streamlit as st
import random
import yaml
import time
from pathlib import Path
from tinydb import TinyDB, Query
from typing import Dict, List, Optional

# Timing utilities
start_time = time.time()


def log_timing(message: str):
    """Log timing information"""
    elapsed = time.time() - start_time
    print(f"[{elapsed:.3f}s] {message}")


log_timing("Starting Secret Santa app - imports loaded")

# Configuration
CONFIG_FILE = Path("config.yaml")
DB_FILE = Path("secret_santa.db")

log_timing("Configuration constants defined")

# Page configuration
log_timing("Setting up Streamlit page config")
st.set_page_config(page_title="Secret Santa", page_icon="🎅", layout="centered")
log_timing("Streamlit page config complete")


# Load configuration
@st.cache_data
def load_config() -> Dict:
    """Load configuration from YAML file"""
    log_timing("Loading configuration file")
    if not CONFIG_FILE.exists():
        st.error(f"Configuration file '{CONFIG_FILE}' not found!")
        st.stop()

    with open(CONFIG_FILE, "r") as f:
        config = yaml.safe_load(f)
    log_timing(
        f"Configuration loaded - {len(config.get('participants', []))} participants"
    )
    return config


# Database functions
def get_db():
    """Get database instance"""
    log_timing("Opening database connection")
    db = TinyDB(DB_FILE)
    log_timing("Database connection established")
    return db


def initialize_assignments(
    participants: List[str], exclusions: Dict[str, List[str]]
) -> Dict[str, str]:
    """Generate Secret Santa assignments ensuring no self-assignments and respecting exclusions

    Args:
        participants: List of participant usernames
        exclusions: Dict mapping username to list of usernames they cannot be assigned to
    """
    log_timing(
        f"Generating new assignments for {len(participants)} participants with exclusions"
    )
    givers = participants.copy()
    receivers = participants.copy()

    # Shuffle until we get a valid assignment
    valid = False
    max_attempts = 1000
    attempts = 0

    while not valid and attempts < max_attempts:
        random.shuffle(receivers)

        # Check all constraints: no self-assignment and no excluded pairs
        valid = True
        for giver, receiver in zip(givers, receivers):
            # Check self-assignment
            if giver == receiver:
                valid = False
                break

            # Check exclusion constraints
            if receiver in exclusions.get(giver, []):
                valid = False
                break

        attempts += 1

    if not valid:
        raise ValueError(
            f"Could not generate valid assignments after {max_attempts} attempts. Check if constraints are too restrictive."
        )

    log_timing(f"Assignments generated after {attempts} attempts")
    return dict(zip(givers, receivers))


def get_or_create_assignments(config: Dict) -> Dict[str, str]:
    """Get assignments from database or create new ones"""
    log_timing("Getting or creating assignments")
    db = get_db()

    # Check if assignments already exist
    assignments_table = db.table("assignments")
    existing = assignments_table.all()

    if existing:
        # Convert list of records to dictionary
        log_timing(f"Found existing assignments - {len(existing)} records")
        return {record["giver"]: record["receiver"] for record in existing}

    # Create new assignments
    log_timing("No existing assignments found, creating new ones")
    usernames = [p["username"] for p in config["participants"]]

    # Build exclusion map
    exclusions = {}
    for p in config["participants"]:
        username = p["username"]
        excluded = p.get("exclude", [])
        if excluded:
            exclusions[username] = excluded
            log_timing(f"  {username} cannot give to: {', '.join(excluded)}")

    assignments = initialize_assignments(usernames, exclusions)

    # Store in database
    log_timing("Storing assignments in database")
    for giver, receiver in assignments.items():
        assignments_table.insert({"giver": giver, "receiver": receiver})
    log_timing("Assignments stored successfully")

    return assignments


def get_wish_list(username: str) -> List[str]:
    """Get wish list for a user"""
    db = get_db()
    wishes_table = db.table("wishes")
    User = Query()
    result = wishes_table.get(User.username == username)
    return result["items"] if result else []


def save_wish_list(username: str, items: List[str]):
    """Save wish list for a user"""
    db = get_db()
    wishes_table = db.table("wishes")
    User = Query()

    if wishes_table.get(User.username == username):
        wishes_table.update({"items": items}, User.username == username)
    else:
        wishes_table.insert({"username": username, "items": items})


# Authentication
def authenticate(username: str, password: str, config: Dict) -> Optional[Dict]:
    """Authenticate user against config file"""
    for participant in config["participants"]:
        if participant["username"] == username and participant["password"] == password:
            return participant
    return None


def get_user_info(username: str, config: Dict) -> Optional[Dict]:
    """Get user information from config"""
    for participant in config["participants"]:
        if participant["username"] == username:
            return participant
    return None


# Initialize session state
log_timing("Initializing session state")
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = None
log_timing("Session state initialized")

# Load configuration
log_timing("Starting configuration load")
config = load_config()

# Initialize assignments on startup
log_timing("Starting assignment initialization")
try:
    assignments = get_or_create_assignments(config)
    log_timing("Assignment initialization complete")

    # Debug: Print assignments to terminal
    print("DEBUG - Secret Santa Assignments:")
    for giver, receiver in assignments.items():
        print(f"  {giver} -> {receiver}")
    print("-" * 40)
except Exception as e:
    st.error(f"Error initializing assignments: {e}")
    st.stop()

# Main app
log_timing("Starting UI rendering")
st.title("🎅 Secret Santa Gift Exchange")

# Login page
log_timing("Rendering login/main UI")
if not st.session_state.authenticated:
    st.write("Please login to see your Secret Santa assignment")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")

        if submit:
            user = authenticate(username, password, config)
            if user:
                st.session_state.authenticated = True
                st.session_state.username = username
                st.rerun()
            else:
                st.error("Invalid username or password")

# Main application (after login)
else:
    log_timing("Rendering authenticated user interface")
    user = get_user_info(st.session_state.username, config)

    # Sidebar
    with st.sidebar:
        st.write(f"### Welcome, {user['name']}! 👋")
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.username = None
            st.rerun()

    # Display budget
    st.info(f"💰 Gift Budget: **${config['budget']}**")

    # Get receiver
    receiver_username = assignments.get(st.session_state.username)
    receiver = get_user_info(receiver_username, config)

    if receiver:
        st.success(f"🎁 You are Secret Santa for: **{receiver['name']}**")
        st.write("Remember to keep it a secret! 🤫")

        # Display receiver's wish list
        st.subheader(f"📝 {receiver['name']}'s Wish List")
        receiver_wishes = get_wish_list(receiver_username)

        if receiver_wishes:
            for i, item in enumerate(receiver_wishes, 1):
                st.write(f"{i}. {item}")
        else:
            st.write(f"*{receiver['name']} hasn't added any wishes yet*")
    else:
        st.error("Could not find your assignment. Please contact the administrator.")

    st.write("---")

    # Manage own wish list
    st.subheader("🎁 Your Wish List")
    st.write("Add items you'd like to receive (your Secret Santa will see this)")

    # Load current wish list
    current_wishes = get_wish_list(st.session_state.username)

    # Display current wishes
    if current_wishes:
        st.write("**Current wishes:**")
        for i, item in enumerate(current_wishes):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"{i + 1}. {item}")
            with col2:
                if st.button("Remove", key=f"remove_{i}"):
                    current_wishes.pop(i)
                    save_wish_list(st.session_state.username, current_wishes)
                    st.rerun()

    # Add new wish
    with st.form("add_wish_form"):
        new_wish = st.text_input("Add a new wish:")
        add_button = st.form_submit_button("Add Wish")

        if add_button and new_wish:
            current_wishes.append(new_wish)
            save_wish_list(st.session_state.username, current_wishes)
            st.success("Wish added!")
            st.rerun()

# Final timing log
log_timing("App rendering complete - ready for user interaction")
