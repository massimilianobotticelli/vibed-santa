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
CONFIG_FILE = Path(".appconfig.yaml")
# Create data directory if it doesn't exist (for Docker volume mounting)
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DB_FILE = DATA_DIR / "secret_santa.db"
TRANSLATIONS_FILE = Path("translations.yaml")

log_timing("Configuration constants defined")


# Load translations from YAML file
@st.cache_data
def load_translations() -> Dict:
    """Load translations from YAML file"""
    log_timing("Loading translations file")
    if not TRANSLATIONS_FILE.exists():
        st.error(f"Translations file '{TRANSLATIONS_FILE}' not found!")
        st.stop()

    with open(TRANSLATIONS_FILE, "r", encoding="utf-8") as f:
        translations_data = yaml.safe_load(f)

    log_timing("Translations loaded")
    return translations_data.get("translations", {})


def get_text(lang: str, key: str) -> str:
    """Get translated text for a given language and key"""
    translations = load_translations()
    return translations.get(key, {}).get(lang, key)


# Page configuration
log_timing("Setting up Streamlit page config")
st.set_page_config(page_title="Secret Santa", page_icon="🎅", layout="centered")
log_timing("Streamlit page config complete")


# Load configuration
def get_config_mtime():
    """Get modification time of config file for cache invalidation"""
    return CONFIG_FILE.stat().st_mtime if CONFIG_FILE.exists() else 0


@st.cache_data(ttl=60)  # Cache for 60 seconds, then reload to pick up config changes
def load_config(_mtime: float) -> Dict:
    """Load configuration from YAML file

    Args:
        _mtime: Modification time of config file (prefixed with _ to exclude from hash)
    """
    log_timing("Loading configuration file")
    if not CONFIG_FILE.exists():
        st.error(f"Configuration file '{CONFIG_FILE}' not found!")
        st.stop()

    with open(CONFIG_FILE, "r") as f:
        config = yaml.safe_load(f)

    num_families = len(config.get("families", []))
    total_participants = sum(
        len(family.get("participants", [])) for family in config.get("families", [])
    )
    log_timing(
        f"Configuration loaded - {num_families} families, {total_participants} total participants"
    )
    return config


def get_family_by_id(config: Dict, family_id: str) -> Optional[Dict]:
    """Get family configuration by ID"""
    for family in config.get("families", []):
        if family["id"] == family_id:
            return family
    return None


def find_user_family(config: Dict, username: str) -> Optional[Dict]:
    """Find which family a user belongs to"""
    for family in config.get("families", []):
        for participant in family.get("participants", []):
            if participant["username"] == username:
                return family
    return None


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


def get_or_create_assignments(family: Dict) -> Dict[str, str]:
    """Get assignments from database or create new ones for a specific family.

    This function is idempotent - it will:
    - Return existing assignments if they exist (preserves previous assignments)
    - Create new assignments only if none exist for this family

    This ensures that:
    - Existing groups keep their assignments unchanged
    - New groups added to config get assignments automatically
    """
    family_id = family["id"]
    log_timing(f"Getting or creating assignments for family: {family_id}")
    db = get_db()

    # Check if assignments already exist for this family
    assignments_table = db.table(f"assignments_{family_id}")
    existing = assignments_table.all()

    if existing:
        # Convert list of records to dictionary
        # IMPORTANT: Existing assignments are NEVER modified
        log_timing(f"Found existing assignments - {len(existing)} records")
        return {record["giver"]: record["receiver"] for record in existing}

    # Create new assignments
    log_timing("No existing assignments found, creating new ones")
    usernames = [p["username"] for p in family["participants"]]

    # Build exclusion map
    exclusions = {}
    for p in family["participants"]:
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
def authenticate(username: str, password: str, family: Dict) -> Optional[Dict]:
    """Authenticate user against config file for a specific family"""
    for participant in family["participants"]:
        if participant["username"] == username and participant["password"] == password:
            return participant
    return None


def get_user_info(username: str, family: Dict) -> Optional[Dict]:
    """Get user information from family config"""
    for participant in family["participants"]:
        if participant["username"] == username:
            return participant
    return None


def initialize_all_families(config: Dict):
    """Initialize assignments for all families in the config at startup.

    This function:
    - Creates assignments for new families
    - Preserves assignments for existing families
    - Removes families from database that are no longer in config
    """
    # Get list of family IDs from config
    config_family_ids = {family["id"] for family in config.get("families", [])}

    db = get_db()

    # Get list of all assignment tables in database
    all_tables = db.tables()
    assignment_tables = [t for t in all_tables if t.startswith("assignments_")]

    # Extract family IDs from table names
    db_family_ids = {t.replace("assignments_", "") for t in assignment_tables}

    # Find families to remove (in DB but not in config)
    families_to_remove = db_family_ids - config_family_ids

    # Remove families that are no longer in config
    if families_to_remove:
        log_timing(f"Found {len(families_to_remove)} families to remove from database")
        for family_id in families_to_remove:
            try:
                db.drop_table(f"assignments_{family_id}")
                log_timing(
                    f"Removed family '{family_id}' from database (no longer in config)"
                )
            except Exception as e:
                print(f"ERROR: Could not remove family '{family_id}': {e}")

    # Close the database connection to ensure changes are persisted
    db.close()

    # Initialize assignments for all families in config
    log_timing(f"Initializing {len(config_family_ids)} families from config")
    for family in config.get("families", []):
        family_id = family["id"]
        try:
            # This will create assignments if they don't exist, or return existing ones
            assignments = get_or_create_assignments(family)
            log_timing(
                f"Family '{family['name']}' ({family_id}): {len(assignments)} assignments ready"
            )
        except Exception as e:
            # Log error but continue with other families
            print(
                f"ERROR: Could not initialize family '{family['name']}' ({family_id}): {e}"
            )

    log_timing("Family initialization complete")


# Initialize session state
log_timing("Initializing session state")
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = None
if "selected_family_id" not in st.session_state:
    st.session_state.selected_family_id = None
if "language" not in st.session_state:
    st.session_state.language = "en"  # Default to English
log_timing("Session state initialized")

# Load configuration
log_timing("Starting configuration load")
config = load_config(get_config_mtime())

# Initialize assignments for all families (create for new families, preserve existing)
initialize_all_families(config)

# Main app
log_timing("Starting UI rendering")

# Login page
log_timing("Rendering login/main UI")
if not st.session_state.authenticated:
    # Language selector with flags at the top

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button(
            "English",
            use_container_width=True,
            type="primary" if st.session_state.language == "en" else "secondary",
        ):
            st.session_state.language = "en"
            st.rerun()

    with col2:
        if st.button(
            "Deutsch",
            use_container_width=True,
            type="primary" if st.session_state.language == "de" else "secondary",
        ):
            st.session_state.language = "de"
            st.rerun()

    with col3:
        if st.button(
            "Italiano",
            use_container_width=True,
            type="primary" if st.session_state.language == "it" else "secondary",
        ):
            st.session_state.language = "it"
            st.rerun()

    lang = st.session_state.language

    st.markdown("---")

    # Use translated title and prompt
    st.title(get_text(lang, "title"))
    st.write(get_text(lang, "login_prompt"))

    # Family selector
    family_options = {f["name"]: f["id"] for f in config["families"]}
    selected_family_name = st.selectbox(
        get_text(lang, "select_family"), list(family_options.keys())
    )
    selected_family_id = family_options[selected_family_name]
    selected_family = get_family_by_id(config, selected_family_id)

    with st.form("login_form"):
        username = st.text_input(get_text(lang, "username"))
        password = st.text_input(get_text(lang, "password"), type="password")
        submit = st.form_submit_button(get_text(lang, "login_button"))

        if submit:
            user = authenticate(username, password, selected_family)
            if user:
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.selected_family_id = selected_family_id
                st.rerun()
            else:
                st.error(get_text(lang, "invalid_credentials"))

    # Display credentials hint
    with st.expander(get_text(lang, "login_info")):
        st.write(
            f"**{get_text(lang, 'available_accounts')} {selected_family['name']}:**"
        )
        for participant in selected_family["participants"]:
            st.write(
                f"- **{participant['name']}** (username: `{participant['username']}`)"
            )

# Main application (after login)
else:
    log_timing("Rendering authenticated user interface")

    # Get current family
    current_family = get_family_by_id(config, st.session_state.selected_family_id)
    if not current_family:
        st.error("Family not found. Please log in again.")
        st.session_state.authenticated = False
        st.rerun()

    lang = st.session_state.language  # Use session language instead of family language
    user = get_user_info(st.session_state.username, current_family)

    # Use translated title
    st.title(get_text(lang, "title"))

    # Get assignments for this family (already initialized at startup)
    try:
        assignments = get_or_create_assignments(current_family)
    except Exception as e:
        st.error(f"Error loading assignments: {e}")
        st.stop()

    # Sidebar
    with st.sidebar:
        st.write(f"### {get_text(lang, 'welcome')}, {user['name']}! 👋")
        st.write(f"**{get_text(lang, 'family')}:** {current_family['name']}")

        # Language selector with flags
        st.markdown("---")
        st.write(f"**🌍 {get_text(lang, 'select_language')}**")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button(
                "EN",
                use_container_width=True,
                type="primary" if lang == "en" else "secondary",
                key="lang_en_sidebar",
            ):
                st.session_state.language = "en"
                st.rerun()

        with col2:
            if st.button(
                "DE",
                use_container_width=True,
                type="primary" if lang == "de" else "secondary",
                key="lang_de_sidebar",
            ):
                st.session_state.language = "de"
                st.rerun()

        with col3:
            if st.button(
                "IT",
                use_container_width=True,
                type="primary" if lang == "it" else "secondary",
                key="lang_it_sidebar",
            ):
                st.session_state.language = "it"
                st.rerun()

        st.markdown("---")
        if st.button(get_text(lang, "logout")):
            st.session_state.authenticated = False
            st.session_state.username = None
            st.session_state.selected_family_id = None
            st.rerun()

    # Display budget
    currency = current_family.get("currency", "$")  # Default to $ if not specified
    st.info(
        f"{get_text(lang, 'gift_budget')}: **{currency}{current_family['budget']}**"
    )

    # Get receiver
    receiver_username = assignments.get(st.session_state.username)
    receiver = get_user_info(receiver_username, current_family)

    if receiver:
        st.success(f"{get_text(lang, 'you_are_santa_for')} **{receiver['name']}**")
        st.write(get_text(lang, "keep_secret"))

        # Display receiver's wish list
        st.subheader(f"{get_text(lang, 'wish_list')} {receiver['name']}")
        receiver_wishes = get_wish_list(receiver_username)

        if receiver_wishes:
            for i, item in enumerate(receiver_wishes, 1):
                st.write(f"{i}. {item}")
        else:
            st.write(f"*{receiver['name']} {get_text(lang, 'no_wishes_yet')}*")
    else:
        st.error(get_text(lang, "assignment_error"))

    st.write("---")

    # Manage own wish list
    st.subheader(get_text(lang, "your_wish_list"))
    st.write(get_text(lang, "wish_list_info"))

    # Load current wish list
    current_wishes = get_wish_list(st.session_state.username)

    # Display current wishes
    if current_wishes:
        st.write(f"**{get_text(lang, 'current_wishes')}**")
        for i, item in enumerate(current_wishes):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"{i + 1}. {item}")
            with col2:
                if st.button(get_text(lang, "remove"), key=f"remove_{i}"):
                    current_wishes.pop(i)
                    save_wish_list(st.session_state.username, current_wishes)
                    st.rerun()

    # Add new wish
    with st.form("add_wish_form"):
        new_wish = st.text_input(get_text(lang, "add_new_wish"))
        add_button = st.form_submit_button(get_text(lang, "add_wish_button"))

        if add_button and new_wish:
            current_wishes.append(new_wish)
            save_wish_list(st.session_state.username, current_wishes)
            st.success(get_text(lang, "wish_added"))
            st.rerun()

# Final timing log
log_timing("App rendering complete - ready for user interaction")
