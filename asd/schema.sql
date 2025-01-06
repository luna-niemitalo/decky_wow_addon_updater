CREATE TABLE if not exists "wanted_addons"
(
    name            text    not null,
    project_id      integer not null,
    desired_version integer default null,
    date            date    default null,
    current_version_id integer default null
);

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
