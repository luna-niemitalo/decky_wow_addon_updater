import os
import sqlite3
import json
from pathlib import Path

import zipfile
import requests
from decky import DECKY_PLUGIN_SETTINGS_DIR

db_path = Path(DECKY_PLUGIN_SETTINGS_DIR) / "local_db.sqlite"

config_path = Path(DECKY_PLUGIN_SETTINGS_DIR) / "config.json"

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

def get_new_versions(project_id, current_version):
    """Get new versions for the given project ID."""
    print(f"Getting new versions for project ID {project_id}...")

    # Load headers from headers.txt
    headers = {}
    with open('headers.txt', 'r') as f:
        for line in f:
            if ':' in line:
                key, value = line.strip().split(':', 1)
                headers[key.strip()] = value.strip()

    url = f"{base_url}{project_id}/files"
    print(url)
    # files?pageIndex=0&pageSize=20&sort=dateCreated&sortDescending=true&removeAlphas=true
    query = {"pageIndex": 0, "pageSize": config['page_size'], "sort": "dateCreated", "sortAscending": True, "removeAlphas": True}
    response = requests.get(url, headers=headers, params=query)
    results = []
    if response.status_code == 200:
        data = response.json()
        for file in data["data"]:
            if not file["isAvailableForDownload"]: continue
            if not current_version or file["id"] > current_version:
                try:
                    gameVersions = file["gameVersions"]
                    gameVersionTypeIds = file["gameVersionTypeIds"]
                    wanted_version_index = gameVersionTypeIds.index(config['game_version'])
                except ValueError:
                    continue
                results.append({
                    "version_id": file["id"],
                    "project_id": project_id,
                    "file_name": file["fileName"],
                    "date_created": file["dateCreated"],
                    "game_version": gameVersions[wanted_version_index]
                })

    return results

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
                if wanted_addon["current_version_id"] is None or addon_description["version_id"] > wanted_addon[
                    "current_version_id"]:
                    latest_versions.append(addon_description)
                    break

    conn.close()
    return latest_versions

def download_new_version(addon_description):
    download_url = f'https://www.curseforge.com/api/v1/mods/{addon_description["project_id"]}/files/{addon_description["version_id"]}/download'
    print(download_url)
    response = requests.get(download_url)
    data = response.content
    path = f"cache/{addon_description['file_name']}"
    with open(path, 'wb') as f:
        f.write(data)


def extract_file(version):
    """Extract the downloaded version to a directory."""
    path = f"cache/{version['file_name']}"
    zip_ref = zipfile.ZipFile(path, 'r')
    zip_ref.extractall(config["target_dir"])
    zip_ref.close()


def update_addon_version_in_db(version_id, project_id):
    """Update the current version ID in the database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE wanted_addons
        SET current_version_id =?, date = CURRENT_TIMESTAMP
        WHERE project_id =?;
    """, (version_id, project_id))
    print(f"Updated current version ID for project ID {project_id} to {version_id}.")
    conn.commit()
    conn.close()


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
    print(f"Added addon with project ID {project_id} and name '{name}' to the database.")


def init_plugin():
    create_db_if_not_exists()
    add_addon_to_db(1171316, "Reverse Engineering")
    return load_wanted_addons_from_sqlite()






def main():
    print("Running debug variant...")
    os.environ["DECKY_DEBUG"] = "1"

    init_plugin()
    add_addon_to_db(61284, "Details")
    return
    db_path = Path(DECKY_PLUGIN_SETTINGS_DIR) / "local_db.sqlite"

    wanted_addons = load_wanted_addons_from_sqlite()
    for addon in wanted_addons:
        project_id = addon["project_id"]
        current_version = addon["current_version_id"]
        new_versions = get_new_versions(project_id, current_version)
        add_versions_to_db(new_versions)

    latest_versions = get_latest_versions(wanted_addons)
    print(json.dumps(latest_versions, indent=4))

    for version in latest_versions:
        download_new_version(version)
        extract_file(version)
        update_addon_version_in_db(version["version_id"], version["project_id"])


if __name__ == "__main__":
    main()
