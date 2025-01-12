import os
import sqlite3
from datetime import datetime
from time import sleep

# The decky plugin module is located at decky-loader/plugin
# For easy intellisense checkout the decky-loader code repo
# and add the `decky-loader/plugin/imports` path to `python.analysis.extraPaths` in `.vscode/settings.json`
import decky
import asyncio
import json
from pathlib import Path
import zipfile
import requests



db_path = Path(decky.DECKY_PLUGIN_SETTINGS_DIR) / "local_db.sqlite"

config_path = Path(decky.DECKY_PLUGIN_SETTINGS_DIR) / "config.json"

mode = 'r' if os.path.exists(config_path) else 'w+'
with open(config_path, mode) as f:
    if mode == 'r':
        config = json.load(f)
    else:
        config = {
            "game_version": 517,
            "page_size": 3,
            "target_dir": "<target_directory(ex ..._retail_/wtf/interface/addOns/)>",
        }
        json.dump(config, f, indent=4)

base_url = "https://www.curseforge.com/api/v1/mods/"
target_dir = config["target_dir"]

def load_wanted_addons_from_sqlite():
    """Load wanted addons from SQLite database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM wanted_addons")
    addons = cursor.fetchall()
    addon_list = []
    for addon in addons:
        [name, project_id, desired_version, date, current_version_id] = addon
        addon_list.append({
            "name": name,
            "project_id": project_id,
            "desired_version": desired_version,
            "date": date,
            "current_version_id": current_version_id
        })

    conn.close()
    return addon_list

def parse_addon_data(project_id, file):
    try:
        gameVersions = file["gameVersions"]
        gameVersionTypeIds = file["gameVersionTypeIds"]
        wanted_version_index = gameVersionTypeIds.index(config['game_version'])
    except ValueError:
        decky.logger.error(f"Value error while parsing addon data for project ID {project_id}.")
        return None
    return {
        "version_id": file["id"],
        "project_id": project_id,
        "file_name": file["fileName"],
        "date_created": file["dateCreated"],
        "game_version": gameVersions[wanted_version_index]
    }

def get_new_versions(project_id, current_version):
    """Get new versions for the given project ID."""
    decky.logger.info(f"Getting new versions for project ID {project_id}: {current_version}...")

    # Load headers from headers.txt
    headers = {}
    try:
        with open('headers.txt', 'r') as f:
            for line in f:
                if ':' in line:
                    key, value = line.strip().split(':', 1)
                    headers[key.strip()] = value.strip()
    except OSError:
        decky.logger.error("Failed to load headers from headers.txt")

    url = f"{base_url}{project_id}/files"
    decky.logger.info(url)
    # files?pageIndex=0&pageSize=20&sort=dateCreated&sortDescending=true&removeAlphas=true
    query = {"pageIndex": 0, "pageSize": config['page_size'], "sort": "dateCreated", "sortAscending": True, "removeAlphas": True, "gameFlavorId": config['game_version']}
    response = requests.get(url, headers=headers, params=query)
    results = []
    if response.status_code == 200:
        data = response.json()
        decky.logger.info(f"Found {data['data']} new versions for project ID {project_id}.")
        for file in data["data"]:
            if not file["isAvailableForDownload"]: continue
            if not current_version or file["id"] > current_version:
                addon_data = parse_addon_data(project_id, file)
                if addon_data:
                    results.append(addon_data)
    else:
        decky.logger.error(f"Failed to get new versions for project ID {project_id}. Status code: {response.status_code}")

    return results

def get_latest_versions(wanted_addons):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    query = """
    SELECT av.*
    FROM addon_versions av
    INNER JOIN (
        SELECT project_id, MAX(version_id) as max_version_id
        FROM addon_versions
        GROUP BY project_id
    ) latest
    ON av.project_id = latest.project_id AND av.version_id = latest.max_version_id
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    latest_versions = []
    for row in rows:
        addon_description = {
            "version_id": row[1],
            "project_id": row[0],
            "file_name": row[2],
            "date_created": row[4],
            "game_version": row[3]
        }
        for wanted_addon in wanted_addons:
            if addon_description["project_id"] == wanted_addon["project_id"]:
                if wanted_addon["current_version_id"] is None:
                    latest_versions.append(addon_description)
                    break
                if addon_description["version_id"] > wanted_addon["current_version_id"]:
                    latest_versions.append(addon_description)
                    break
    conn.close()
    return latest_versions

def add_versions_to_db(new_versions):
    """Add new versions to SQLite database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for version in new_versions:
        cursor.execute("""
            INSERT OR ignore INTO addon_versions (version_id, project_id, file_name, date_created, game_version)  
            VALUES (?,?,?,?,?);
        """, (version["version_id"], version["project_id"], version["file_name"], version["date_created"], version["game_version"]))

    conn.commit()
    conn.close()

def update_addon_version_in_db(version_id, project_id):
    """Update the current version ID in the database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE wanted_addons
        SET current_version_id =?, date = CURRENT_TIMESTAMP
        WHERE project_id =?;
    """, (version_id, project_id))
    decky.logger.info(f"Updated current version ID for project ID {project_id} to {version_id}.")
    conn.commit()
    conn.close()

def download_new_version(addon_description):
    decky.logger.info(f"Downloading new version for project ID {addon_description['project_id']} version ID {addon_description['version_id']}...")
    download_url = f'https://www.curseforge.com/api/v1/mods/{addon_description["project_id"]}/files/{addon_description["version_id"]}/download'
    decky.logger.info(f"Download URL: {download_url}")
    decky.logger.info(download_url)
    response = requests.get(download_url)
    data = response.content
    download_dir = Path(decky.DECKY_PLUGIN_RUNTIME_DIR) / 'cache' / addon_description['file_name']
    decky.logger.info(download_dir)
    download_dir.parent.mkdir(exist_ok=True, parents=True)
    download_dir.write_bytes(data)
def extract_file(version):
    """Extract the downloaded version to a directory."""
    download_dir = Path(decky.DECKY_PLUGIN_RUNTIME_DIR) / 'cache' / version['file_name']
    decky.logger.info(f"Extracting new version for project ID {version['project_id']} version ID {version['version_id']}..." + download_dir.name)

    zip_ref = zipfile.ZipFile(download_dir, 'r')
    zip_ref.extractall(config["target_dir"])
    zip_ref.close()


def create_db_if_not_exists():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    wanted_addons_table = """
CREATE TABLE if not exists "wanted_addons"
    (
        name            text    not null,
        project_id      integer unique not null,
        desired_version integer default null,
        date            date    default null,
        current_version_id integer default null
    );
"""

    addon_versions_table = """

CREATE TABLE if not exists "addon_versions"
(
    project_id   integer not null
        constraint addon_versions_wanted_addons_project_id_fk
            references wanted_addons (project_id),
    version_id   integer not null
        constraint addon_versions_pk
            primary key,
    file_name    text,
    game_version text,
    date_created date
);
"""
    cursor.execute(wanted_addons_table)
    cursor.execute(addon_versions_table)

    conn.commit()
    conn.close()

def add_addon_to_db(project_id, name):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO wanted_addons (project_id, name)
        VALUES (?,?);
    """, (project_id, name))

    conn.commit()
    conn.close()
    decky.logger.info(f"Added addon with project ID {project_id} and name '{name}' to the database.")


def add_essentials():
    add_addon_to_db(914482, "Baganator")
    add_addon_to_db(91376, "ConsolePort")
    add_addon_to_db(3358, "DBM")
    add_addon_to_db(99861, "DejaCharacterStats")
    add_addon_to_db(61284, "Details")
    add_addon_to_db(261459, "FasterLoot")
    add_addon_to_db(257550, "Immersion")
    add_addon_to_db(4646, "Pawn")
    add_addon_to_db(7473, "Prat-3.0")
    add_addon_to_db(15936, "SexyMap")
    add_addon_to_db(295182, "SpeedyAutoLoot")



def add_addons():
    add_addon_to_db(88589, "AlreadyKnown")
    add_addon_to_db(13402, "Altoholic")
    add_addon_to_db(6124, "Auctionator")
    add_addon_to_db(914482, "Baganator")
    add_addon_to_db(91376, "ConsolePort")
    add_addon_to_db(705015, "CraftSim")
    add_addon_to_db(3358, "DBM")
    add_addon_to_db(99861, "DejaCharacterStats")
    add_addon_to_db(61284, "Details")
    add_addon_to_db(261459, "FasterLoot")
    add_addon_to_db(406104, "GatheringTracker")
    add_addon_to_db(257550, "Immersion")
    add_addon_to_db(94855, "Leatrix_Plus")
    add_addon_to_db(30961, "MogIt")
    add_addon_to_db(269544, "NameplateSCT")
    add_addon_to_db(311718, "Narcissus")
    add_addon_to_db(4646, "Pawn")
    add_addon_to_db(7473, "Prat-3.0")
    add_addon_to_db(15936, "SexyMap")
    add_addon_to_db(295182, "SpeedyAutoLoot")
    add_addon_to_db(988370, "Syndicator")
    add_addon_to_db(26886, "TradeSkillMaster")
    add_addon_to_db(437378, "TrueStatValues")
    add_addon_to_db(1069992, "WarbandMiser")
    add_addon_to_db(267285, "ALL THE THINGS")
    add_addon_to_db(102896, "Premade Groups Filter")
    add_addon_to_db(888580, "Plumber")
    add_addon_to_db(26120, "GatherMate2")
    add_addon_to_db(401253, "Better Wardrobe and Transmog")
    add_addon_to_db(15226, "Grid2")
    add_addon_to_db(86372, "Mount Journal Enhanced")
    add_addon_to_db(29767, "FarmHud")
    add_addon_to_db(30801, "Rarity")
def init_plugin():
    create_db_if_not_exists()
    return load_wanted_addons_from_sqlite()



class Plugin:

    async def check_for_updates(self):
        sleep(10)
        decky.logger.info("Checking for updates... @" + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        await decky.emit("new_versions_found", 1)
        return [{
            "version_id": 99999999999,
            "project_id": 13402,
            "file_name": "Topkek",
        }]
        wanted_addons = load_wanted_addons_from_sqlite()
        for addon in wanted_addons:
            project_id = addon["project_id"]
            current_version = addon["current_version_id"]
            new_versions = get_new_versions(project_id, current_version)
            add_versions_to_db(new_versions)
        latest_versions = get_latest_versions(wanted_addons)
        if latest_versions:
            await decky.emit("new_versions_found", len(latest_versions))
            return latest_versions
        return []

    async def get_versions_from_config(self):
        return decky.DECKY_PLUGIN_VERSION

    async def upgrade_addon(self, version):
        download_new_version(version)
        extract_file(version)
        update_addon_version_in_db(version["version_id"], version["project_id"])
        return load_wanted_addons_from_sqlite()

    async def upgrade_all(self):
        latest_versions = get_latest_versions(load_wanted_addons_from_sqlite())
        for version in latest_versions:
            download_new_version(version)
            extract_file(version)
            update_addon_version_in_db(version["version_id"], version["project_id"])
        return load_wanted_addons_from_sqlite()



    async def list_addons(self):
        # Return a list of addons and their details
        return load_wanted_addons_from_sqlite()
    async def get_addons_with_updates(self):
        wanted_addons = load_wanted_addons_from_sqlite()
        return get_latest_versions(wanted_addons)

    async def install_essentials(self):
        add_essentials()
        return load_wanted_addons_from_sqlite()



    # Asyncio-compatible long-running code, executed in a task when the plugin is loaded
    async def _main(self):
        init_plugin()
        #self.loop = asyncio.get_event_loop()

    # Function called first during the unload process, utilize this to handle your plugin being stopped, but not
    # completely removed
    async def _unload(self):
        pass

    # Function called after `_unload` during uninstall, utilize this to clean up processes and other remnants of your
    # plugin that may remain on the system
    async def _uninstall(self):
        decky.logger.info("Goodbye World!")
        pass

    # Migrations that should be performed before entering `_main()`.
    async def _migration(self):
        decky.logger.info("Migrating")
        # Here's a migration example for logs:
        # - `~/.config/decky-template/template.log` will be migrated to `decky.decky_LOG_DIR/template.log`
        decky.migrate_logs(os.path.join(decky.DECKY_USER_HOME,
                                               ".config", "decky-template", "template.log"))
        # Here's a migration example for settings:
        # - `~/homebrew/settings/template.json` is migrated to `decky.decky_SETTINGS_DIR/template.json`
        # - `~/.config/decky-template/` all files and directories under this root are migrated to `decky.decky_SETTINGS_DIR/`
        decky.migrate_settings(
            os.path.join(decky.DECKY_HOME, "settings", "template.json"),
            os.path.join(decky.DECKY_USER_HOME, ".config", "decky-template"))
        # Here's a migration example for runtime data:
        # - `~/homebrew/template/` all files and directories under this root are migrated to `decky.decky_RUNTIME_DIR/`
        # - `~/.local/share/decky-template/` all files and directories under this root are migrated to `decky.decky_RUNTIME_DIR/`
        decky.migrate_runtime(
            os.path.join(decky.DECKY_HOME, "template"),
            os.path.join(decky.DECKY_USER_HOME, ".local", "share", "decky-template"))
