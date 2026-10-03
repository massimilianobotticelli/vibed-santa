import streamlit as st
import yaml
import time
from datetime import datetime
from pathlib import Path
from tinydb import TinyDB
from typing import Dict, List, Optional

import admin
import draws
import groups
import reset
import wishes

# Timing utilities
start_time = time.time()


def log_timing(message: str):
    """Log timing information"""
    elapsed = time.time() - start_time
    print(f"[{elapsed:.3f}s] {message}")


log_timing("Starting Secret Santa app - imports loaded")

# Configuration
# Create data directory if it doesn't exist (for Docker volume mounting)
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DB_FILE = DATA_DIR / "secret_santa.db"
# YAML configuration of older versions, imported into an empty database
IMPORT_FILE = DATA_DIR / "appconfig.yaml"
TRANSLATIONS_FILE = Path("translations.yaml")
LANGUAGES = {"en": "English", "de": "Deutsch", "it": "Italiano"}

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


def get_family_by_id(config: Dict, family_id: str) -> Optional[Dict]:
    """Get family configuration by ID"""
    for family in config.get("families", []):
        if family["id"] == family_id:
            return family
    return None


# Database functions
def get_db():
    """Get database instance"""
    log_timing("Opening database connection")
    db = TinyDB(DB_FILE)
    log_timing("Database connection established")
    return db


def get_wish_list(family_id: str, username: str) -> List[str]:
    """Get wish list for a user within a specific family"""
    return wishes.get_wish_list(get_db(), family_id, username)


def save_wish_list(family_id: str, username: str, items: List[str]):
    """Save wish list for a user within a specific family"""
    wishes.save_wish_list(get_db(), family_id, username, items)


def import_config_file(db: TinyDB):
    """Import groups and people from the YAML configuration of older versions"""
    if not IMPORT_FILE.is_file():
        return

    with open(IMPORT_FILE, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    if groups.import_config(db, config):
        IMPORT_FILE.rename(IMPORT_FILE.with_name(IMPORT_FILE.name + ".imported"))
        log_timing(f"Imported groups and people from '{IMPORT_FILE}'")
    else:
        log_timing(f"Ignoring '{IMPORT_FILE}': the database already has groups")


def prepare_database() -> Dict:
    """Bring data stored by older versions of the app up to date

    Returns:
        The groups, in the structure of the YAML configuration of older versions
    """
    db = get_db()
    import_config_file(db)
    config = groups.build_config(db)

    migrated = draws.migrate_legacy_assignments(db)
    if migrated:
        log_timing(f"Migrated {migrated} legacy assignment tables to draws")

    # Wish lists used to be shared across families; scope old ones per family
    migrated = wishes.migrate_legacy_wishes(db, config)
    if migrated:
        log_timing(f"Migrated {migrated} legacy wish lists to per-family wish lists")

    # Close the database connection to ensure changes are persisted
    db.close()
    return config


# Authentication
def get_user_info(username: str, family: Dict) -> Optional[Dict]:
    """Get user information from family config"""
    for participant in family["participants"]:
        if participant["username"] == username:
            return participant
    return None


def logout():
    """Log out the participant or the admin"""
    st.session_state.authenticated = False
    st.session_state.username = None
    st.session_state.selected_family_id = None
    st.session_state.is_admin = False
    st.rerun()


# UI components
def language_selector(sidebar: bool):
    """Render one button per language (language codes only in the sidebar)"""
    for col, (code, label) in zip(st.columns(len(LANGUAGES)), LANGUAGES.items()):
        with col:
            if st.button(
                code.upper() if sidebar else label,
                use_container_width=True,
                type="primary" if st.session_state.language == code else "secondary",
                key=f"lang_{code}_{'sidebar' if sidebar else 'main'}",
            ):
                st.session_state.language = code
                st.rerun()


def sidebar(lang: str, greeting: str):
    """Render the sidebar of a logged-in user"""
    with st.sidebar:
        st.write(greeting)

        st.markdown("---")
        st.write(f"**🌍 {get_text(lang, 'select_language')}**")
        language_selector(sidebar=True)

        st.markdown("---")
        if st.button(get_text(lang, "logout")):
            logout()


def format_draw_date(drawn_at: str) -> str:
    """Format the ISO timestamp of a draw for display"""
    return datetime.fromisoformat(drawn_at).strftime("%Y-%m-%d %H:%M UTC")


# Pages
def render_admin_setup(lang: str):
    """First start: create the admin account"""
    language_selector(sidebar=False)
    st.markdown("---")

    st.title(get_text(lang, "admin_setup_title"))
    st.write(get_text(lang, "admin_setup_info"))

    if "flash" in st.session_state:
        st.success(st.session_state.pop("flash"))

    with st.form("admin_setup_form"):
        username = st.text_input(get_text(lang, "username"))
        password = st.text_input(get_text(lang, "password"), type="password")
        confirm = st.text_input(get_text(lang, "confirm_password"), type="password")
        submit = st.form_submit_button(get_text(lang, "create_admin_button"))

        if submit:
            if not username.strip() or not password:
                st.error(get_text(lang, "fields_required"))
            elif password != confirm:
                st.error(get_text(lang, "passwords_do_not_match"))
            else:
                try:
                    admin.create_admin(get_db(), username.strip(), password)
                    st.session_state.is_admin = True
                except ValueError:
                    # Someone else created the admin account in the meantime
                    pass
                st.rerun()


def render_participant_login(lang: str):
    """Login form for participants"""
    st.write(get_text(lang, "login_prompt"))

    with st.form("login_form"):
        username = st.text_input(get_text(lang, "username"), key="login_username")
        password = st.text_input(
            get_text(lang, "password"), type="password", key="login_password"
        )
        submit = st.form_submit_button(get_text(lang, "login_button"))

        if submit:
            person = groups.authenticate(get_db(), username, password)
            if person:
                st.session_state.authenticated = True
                st.session_state.username = person["username"]
                st.session_state.selected_family_id = None  # First group of the user
                st.rerun()
            else:
                st.error(get_text(lang, "invalid_credentials"))


def render_login(lang: str):
    """Login page for participants and admin"""
    language_selector(sidebar=False)
    st.markdown("---")

    st.title(get_text(lang, "title"))
    participant_tab, admin_tab = st.tabs(
        [get_text(lang, "participant_tab"), get_text(lang, "admin_tab")]
    )

    with participant_tab:
        render_participant_login(lang)

    with admin_tab:
        with st.form("admin_login_form"):
            username = st.text_input(get_text(lang, "username"), key="admin_username")
            password = st.text_input(
                get_text(lang, "password"), type="password", key="admin_password"
            )
            submit = st.form_submit_button(get_text(lang, "login_button"))

            if submit:
                if admin.verify_admin(get_db(), username, password):
                    st.session_state.is_admin = True
                    st.rerun()
                else:
                    st.error(get_text(lang, "invalid_admin_credentials"))


def switch_family():
    """Show the family picked in the group switcher of the personal page"""
    st.session_state.selected_family_id = st.session_state.group_switcher


def render_participant(config: Dict, lang: str):
    """Assignment and wish list of a logged-in participant"""
    log_timing("Rendering authenticated user interface")

    person = groups.get_person(get_db(), st.session_state.username)
    if not person:
        # The admin deleted this person
        logout()

    st.title(get_text(lang, "title"))
    welcome = f"### {get_text(lang, 'welcome')}, {person['name']}! 👋"

    user_families = [
        family
        for family in config["families"]
        if get_user_info(person["username"], family)
    ]
    if not user_families:
        sidebar(lang, welcome)
        st.info(get_text(lang, "not_in_any_group"))
        return

    # Stay in the selected family, unless the user is no longer part of it
    family_names = {f["id"]: f["name"] for f in user_families}
    if st.session_state.selected_family_id not in family_names:
        st.session_state.selected_family_id = user_families[0]["id"]

    if len(user_families) > 1:
        st.radio(
            get_text(lang, "your_groups"),
            list(family_names),
            index=list(family_names).index(st.session_state.selected_family_id),
            format_func=family_names.get,
            horizontal=True,
            key="group_switcher",
            on_change=switch_family,
        )

    current_family = get_family_by_id(config, st.session_state.selected_family_id)
    sidebar(
        lang,
        f"{welcome}\n\n**{get_text(lang, 'family')}:** {current_family['name']}",
    )

    # Display budget
    currency = current_family.get("currency", "$")  # Default to $ if not specified
    st.info(
        f"{get_text(lang, 'gift_budget')}: **{currency}{current_family['budget']}**"
    )

    draw = draws.get_draw(get_db(), current_family["id"])
    if draw is None:
        st.info(get_text(lang, "draw_pending"))
    else:
        receiver_username = draw["assignments"].get(st.session_state.username)
        receiver = (
            get_user_info(receiver_username, current_family)
            if receiver_username
            else None
        )

        if receiver:
            st.success(f"{get_text(lang, 'you_are_santa_for')} **{receiver['name']}**")
            st.write(get_text(lang, "keep_secret"))

            # Display receiver's wish list
            st.subheader(f"{get_text(lang, 'wish_list')} {receiver['name']}")
            receiver_wishes = get_wish_list(current_family["id"], receiver_username)

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
    current_wishes = get_wish_list(current_family["id"], st.session_state.username)

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
                    save_wish_list(
                        current_family["id"], st.session_state.username, current_wishes
                    )
                    st.rerun()

    # Add new wish
    with st.form("add_wish_form"):
        new_wish = st.text_input(get_text(lang, "add_new_wish"))
        add_button = st.form_submit_button(get_text(lang, "add_wish_button"))

        if add_button and new_wish:
            current_wishes.append(new_wish)
            save_wish_list(
                current_family["id"], st.session_state.username, current_wishes
            )
            st.success(get_text(lang, "wish_added"))
            st.rerun()


def run_draw(family: Dict, lang: str):
    """Run the draw of a family from the admin console"""
    try:
        draws.run_draw(get_db(), family)
    except ValueError as e:
        st.error(f"{get_text(lang, 'draw_failed')} {e}")
        return

    log_timing(f"Draw completed for family '{family['id']}'")
    st.session_state[f"draw_completed_{family['id']}"] = True
    st.session_state.pop(f"redo_confirm_{family['id']}", None)
    st.rerun()


def render_family_admin(family: Dict, lang: str):
    """Draw status, missing wish lists and (hidden) results of one family"""
    family_id = family["id"]
    participants = family["participants"]
    names = {p["username"]: p["name"] for p in participants}
    currency = family.get("currency", "$")
    db = get_db()

    st.subheader(family["name"])
    st.caption(
        f"{len(participants)} {get_text(lang, 'participants')} · "
        f"{get_text(lang, 'gift_budget')}: {currency}{family['budget']}"
    )

    if st.session_state.pop(f"draw_completed_{family_id}", False):
        st.success(get_text(lang, "draw_success"))

    # Draw
    draw = draws.get_draw(db, family_id)
    if draw is None:
        st.warning(get_text(lang, "draw_not_done"))
        if st.button(get_text(lang, "run_draw"), key=f"draw_{family_id}", type="primary"):
            run_draw(family, lang)
    else:
        if draw["drawn_at"]:
            st.write(
                f"✅ {get_text(lang, 'draw_done')} {format_draw_date(draw['drawn_at'])}"
            )
        else:
            st.write(f"✅ {get_text(lang, 'draw_date_unknown')}")

        if draws.participants_changed(draw, family):
            st.warning(get_text(lang, "participants_changed"))

        with st.expander(get_text(lang, "redo_draw")):
            st.write(get_text(lang, "redo_draw_warning"))
            confirmed = st.checkbox(
                get_text(lang, "redo_draw_confirm"), key=f"redo_confirm_{family_id}"
            )
            if st.button(
                get_text(lang, "redo_draw"),
                key=f"redo_{family_id}",
                disabled=not confirmed,
            ):
                run_draw(family, lang)

    # Wish lists
    missing = [
        p["name"]
        for p in participants
        if not wishes.get_wish_list(db, family_id, p["username"])
    ]
    st.write(
        f"**{get_text(lang, 'wishes_progress')}:** "
        f"{len(participants) - len(missing)}/{len(participants)}"
    )
    if missing:
        st.write(get_text(lang, "missing_wishes"))
        for name in missing:
            st.write(f"- {name}")
    else:
        st.write(get_text(lang, "all_wishes_added"))

    # Results, hidden unless the admin explicitly asks for them
    if draw is not None and st.toggle(
        get_text(lang, "show_results"), key=f"reveal_{family_id}"
    ):
        st.table(
            [
                {
                    get_text(lang, "giver"): names.get(giver, giver),
                    get_text(lang, "receiver"): names.get(receiver, receiver),
                }
                for giver, receiver in draw["assignments"].items()
            ]
        )


def flash(message: str):
    """Show a success message after the next rerun"""
    st.session_state.flash = message
    st.rerun()


def delete_button(lang: str, key: str, label_key: str, warning_key: str) -> bool:
    """Delete button that only works after ticking a confirmation checkbox"""
    st.caption(get_text(lang, warning_key))
    confirmed = st.checkbox(get_text(lang, "confirm_delete"), key=f"confirm_{key}")
    return st.button(
        f"🗑️ {get_text(lang, label_key)}", key=key, disabled=not confirmed
    )


def render_groups_admin(config: Dict, lang: str):
    """Create, edit and delete groups"""
    db = get_db()
    people = groups.list_people(db)
    names = {p["username"]: p["name"] for p in people}

    if not people:
        st.info(get_text(lang, "no_people_yet"))

    with st.expander(get_text(lang, "create_group"), expanded=not config["families"]):
        with st.form("add_group_form", clear_on_submit=True):
            name = st.text_input(get_text(lang, "group_name"))
            col1, col2 = st.columns(2)
            budget = col1.number_input(
                get_text(lang, "budget"), min_value=0.0, value=30.0, step=5.0, format="%g"
            )
            currency = col2.text_input(get_text(lang, "currency"), value="€")
            members = st.multiselect(
                get_text(lang, "members"), list(names), format_func=names.get
            )

            if st.form_submit_button(get_text(lang, "create_group")):
                if not name.strip():
                    st.error(get_text(lang, "name_required"))
                else:
                    groups.add_group(db, name, budget, currency, members)
                    flash(f"{get_text(lang, 'group_created')} {name}")

    for group in groups.list_groups(db):
        group_id = group["id"]
        members = [m for m in group["members"] if m in names]
        with st.expander(
            f"**{group['name']}** · {len(members)} {get_text(lang, 'participants')}"
        ):
            with st.form(f"edit_group_{group_id}"):
                name = st.text_input(get_text(lang, "group_name"), value=group["name"])
                col1, col2 = st.columns(2)
                budget = col1.number_input(
                    get_text(lang, "budget"),
                    min_value=0.0,
                    value=float(group["budget"]),
                    step=5.0,
                    format="%g",
                )
                currency = col2.text_input(
                    get_text(lang, "currency"), value=group["currency"]
                )
                members = st.multiselect(
                    get_text(lang, "members"),
                    list(names),
                    default=members,
                    format_func=names.get,
                )

                if st.form_submit_button(get_text(lang, "save")):
                    if not name.strip():
                        st.error(get_text(lang, "name_required"))
                    else:
                        groups.update_group(
                            db, group_id, name, budget, currency, members
                        )
                        flash(f"{get_text(lang, 'saved')} {name}")

            if delete_button(
                lang, f"delete_group_{group_id}", "delete_group", "delete_group_warning"
            ):
                groups.delete_group(db, group_id)
                flash(f"{get_text(lang, 'deleted')} {group['name']}")


def render_people_admin(lang: str):
    """Add, edit and delete people, and show their logins"""
    db = get_db()
    people = groups.list_people(db)
    names = {p["username"]: p["name"] for p in people}
    all_groups = groups.list_groups(db)
    group_names = {g["id"]: g["name"] for g in all_groups}

    def groups_of(username: str) -> List[str]:
        return [g["id"] for g in all_groups if username in g["members"]]

    with st.expander(get_text(lang, "add_person"), expanded=not people):
        with st.form("add_person_form", clear_on_submit=True):
            name = st.text_input(get_text(lang, "name"))
            col1, col2 = st.columns(2)
            username = col1.text_input(get_text(lang, "username_optional"))
            password = col2.text_input(get_text(lang, "password_optional"))
            exclude = st.multiselect(
                get_text(lang, "exclusions"), list(names), format_func=names.get
            )
            group_ids = st.multiselect(
                get_text(lang, "groups"), list(group_names), format_func=group_names.get
            )

            if st.form_submit_button(get_text(lang, "add_person")):
                if not name.strip():
                    st.error(get_text(lang, "name_required"))
                else:
                    try:
                        person = groups.add_person(db, name, username, password)
                    except ValueError:
                        st.error(get_text(lang, "username_taken"))
                    else:
                        groups.set_exclusions(db, person["username"], exclude)
                        groups.set_person_groups(db, person["username"], group_ids)
                        flash(f"{get_text(lang, 'person_added')} {person['name']}")

    if not people:
        return

    # All logins at once, handy to share them
    if st.toggle(get_text(lang, "show_logins"), key="show_logins"):
        st.dataframe(
            [
                {
                    get_text(lang, "name"): p["name"],
                    get_text(lang, "username"): p["username"],
                    get_text(lang, "password"): p["password"],
                    get_text(lang, "groups"): ", ".join(
                        group_names[g] for g in groups_of(p["username"])
                    ),
                }
                for p in people
            ],
            hide_index=True,
        )

    for person in people:
        username = person["username"]
        person_groups = groups_of(username)
        others = {u: n for u, n in names.items() if u != username}
        with st.expander(
            f"**{person['name']}** · "
            + (
                ", ".join(group_names[g] for g in person_groups)
                or get_text(lang, "no_group")
            )
        ):
            st.write(get_text(lang, "share_login"))
            st.code(
                f"{get_text(lang, 'title')}\n"
                f"{get_text(lang, 'username')}: {username}\n"
                f"{get_text(lang, 'password')}: {person['password']}",
                language=None,
            )
            if st.button(get_text(lang, "new_password"), key=f"new_password_{username}"):
                groups.update_person(db, username, password=groups.generate_password())
                flash(f"{get_text(lang, 'password_generated')} {person['name']}")

            with st.form(f"edit_person_{username}"):
                name = st.text_input(get_text(lang, "name"), value=person["name"])
                password = st.text_input(
                    get_text(lang, "password"), value=person["password"]
                )
                exclude = st.multiselect(
                    get_text(lang, "exclusions"),
                    list(others),
                    default=[e for e in person["exclude"] if e in others],
                    format_func=others.get,
                )
                group_ids = st.multiselect(
                    get_text(lang, "groups"),
                    list(group_names),
                    default=person_groups,
                    format_func=group_names.get,
                )

                if st.form_submit_button(get_text(lang, "save")):
                    if not name.strip() or not password.strip():
                        st.error(get_text(lang, "fields_required"))
                    else:
                        groups.update_person(db, username, name=name, password=password)
                        groups.set_exclusions(db, username, exclude)
                        groups.set_person_groups(db, username, group_ids)
                        flash(f"{get_text(lang, 'saved')} {name}")

            if delete_button(
                lang,
                f"delete_person_{username}",
                "delete_person",
                "delete_person_warning",
            ):
                groups.delete_person(db, username)
                flash(f"{get_text(lang, 'deleted')} {person['name']}")


def render_reset_admin(lang: str):
    """Start a new round or delete all data, after a backup of the database"""
    db = get_db()

    st.subheader(get_text(lang, "reset_round"))
    st.write(get_text(lang, "reset_round_info"))
    confirmed = st.checkbox(
        get_text(lang, "reset_round_confirm"), key="confirm_reset_round"
    )
    if st.button(
        f"🔄 {get_text(lang, 'reset_round')}", key="reset_round", disabled=not confirmed
    ):
        backup_file = reset.backup(DB_FILE)
        reset.reset_round(db)
        log_timing(f"New round started, backup saved to '{backup_file}'")
        st.session_state.pop("confirm_reset_round", None)
        flash(f"{get_text(lang, 'reset_round_done')} {backup_file}")

    st.markdown("---")

    st.subheader(get_text(lang, "reset_all"))
    st.error(get_text(lang, "reset_all_info"))
    with st.form("reset_all_form", clear_on_submit=True):
        password = st.text_input(get_text(lang, "admin_password"), type="password")
        confirmed = st.checkbox(get_text(lang, "reset_all_confirm"))

        if st.form_submit_button(f"🗑️ {get_text(lang, 'reset_all')}"):
            if not confirmed:
                st.error(get_text(lang, "reset_all_not_confirmed"))
            elif not admin.verify_admin_password(db, password):
                st.error(get_text(lang, "wrong_password"))
            else:
                backup_file = reset.backup(DB_FILE)
                reset.reset_all(db)
                log_timing(f"All data deleted, backup saved to '{backup_file}'")
                st.session_state.is_admin = False
                flash(f"{get_text(lang, 'reset_all_done')} {backup_file}")


def render_admin_console(config: Dict, lang: str):
    """Admin console: draws, groups and people"""
    log_timing("Rendering admin console")

    st.title(get_text(lang, "admin_console"))
    st.write(get_text(lang, "admin_console_info"))
    sidebar(lang, f"### {get_text(lang, 'admin_tab')} 🛠️")

    if "flash" in st.session_state:
        st.success(st.session_state.pop("flash"))

    sections = {
        "draws": get_text(lang, "section_draws"),
        "groups": get_text(lang, "section_groups"),
        "people": get_text(lang, "section_people"),
        "reset": get_text(lang, "section_reset"),
    }
    section = st.radio(
        "section",
        list(sections),
        format_func=sections.get,
        horizontal=True,
        key="admin_section",
        label_visibility="collapsed",
    )

    if section == "groups":
        render_groups_admin(config, lang)
    elif section == "people":
        render_people_admin(lang)
    elif section == "reset":
        render_reset_admin(lang)
    else:
        if not config["families"]:
            st.info(get_text(lang, "no_groups_admin"))
        for family in config["families"]:
            st.markdown("---")
            render_family_admin(family, lang)


# Initialize session state
log_timing("Initializing session state")
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = None
if "selected_family_id" not in st.session_state:
    st.session_state.selected_family_id = None
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False
if "language" not in st.session_state:
    st.session_state.language = "en"  # Default to English
log_timing("Session state initialized")

# Load groups and migrate data stored by older versions of the app
config = prepare_database()

# Main app
log_timing("Rendering UI")
lang = st.session_state.language

if not admin.admin_exists(get_db()):
    render_admin_setup(lang)
elif st.session_state.is_admin:
    render_admin_console(config, lang)
elif not st.session_state.authenticated:
    render_login(lang)
else:
    render_participant(config, lang)

# Final timing log
log_timing("App rendering complete - ready for user interaction")
