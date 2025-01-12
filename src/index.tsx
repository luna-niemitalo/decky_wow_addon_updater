import {
    ButtonItem, PanelSection, PanelSectionRow, //Navigation,
    staticClasses
} from "@decky/ui";
import {
    addEventListener, removeEventListener, callable, definePlugin, toaster, // routerHook
} from "@decky/api"
import {useState} from "react";
import {FaShip} from "react-icons/fa";

// import logo from "../assets/logo.png";

// This function calls the python function "add", which takes in two numbers and returns their sum (as a number)
// Note the type annotations:
//  the first one: [first: number, second: number] is for the arguments
//  the second one: number is for the return value

interface IAddonVersionInfo {
    version_id: number,
    project_id: number,
    "file_name": string,
    "date_created": string,
    "game_version": string,
}

interface IAddonInfo {
    name: string,
    project_id: number,
    desired_version: number,
    date: string,
    current_version_id: number,
}

const get_version = callable<[], string>("get_versions_from_config");

const list_addons = callable<[], IAddonInfo[]>("list_addons");
const upgrade_addon_remote = callable<[IAddonVersionInfo], IAddonInfo[]>("upgrade_addon");

const check_for_updates = callable<[], IAddonVersionInfo[]>("check_for_updates");
const install_essentials = callable<[], IAddonInfo[]>("install_essentials");
const start_scheduler = callable<[], void>("start_scheduler_remote");


// This function calls the python function "start_timer", which takes in no arguments and returns nothing.

// It starts a (python) timer which eventually emits the event 'timer_event'
const update_all = callable<[], IAddonInfo[]>("upgrade_all");





function Content() {
    const [addonList, setAddonList] = useState<IAddonInfo[]>([]);
    const [newVersions, setnewVersions] = useState<IAddonVersionInfo[]>([]);

    const upgrade_addon = async (version: IAddonVersionInfo) => {
        const result = await upgrade_addon_remote(version);
        setAddonList(result);
    }

    function get_updates(info: IAddonInfo, versions: IAddonVersionInfo[]) {
        const results = versions.filter(v => v.version_id > info.current_version_id && v.project_id === info.project_id).pop()
        if (!results) return <div>No updates available</div>;
        return <ButtonItem layout="below" onClick={() => upgrade_addon(results)} >Upgrade:<br/> {info.current_version_id + "->" +  results.version_id}</ButtonItem>
    }

    function AddonInfo(info: IAddonInfo, versions: IAddonVersionInfo[]): JSX.Element {
        return (
            <div
                className={staticClasses.PanelSectionRow}
            >
                <h2 className={staticClasses.PanelSectionTitle}>
                    {info.name}
                </h2>
                <p className={staticClasses.Text}>Project ID: {info.project_id}</p>
                <p className={staticClasses.Text}>Desired Version: {info.desired_version}</p>
                <p className={staticClasses.Text}>Date: {info.date}</p>
                <p className={staticClasses.Text}>Current Version ID: {info.current_version_id}</p>
                <p className={staticClasses.Text}>Available Updates:</p>
                <ul>
                    {
                        get_updates(info, versions)
                    }
                </ul>
            </div>
        )
            ;
    }
    const onAddonList = async () => {
        const result = await list_addons();
        setAddonList(result);
    };
    onAddonList();

    const checkForUpdates = async () => {
        const result = await check_for_updates();
        setnewVersions(result);
    };
    const addEssentials = async () => {
        const result = await install_essentials();
        setAddonList(result);
    };
    const updateAll = async () => {
        const result = await update_all();
        setAddonList(result);
    };

    return (<PanelSection title="Panel Section">
        <PanelSectionRow>
            Available updates: {newVersions.length }
        </PanelSectionRow>
        <PanelSectionRow>
            <ButtonItem
                layout="below"
                onClick={addEssentials}
            >
                {"Add essentials"}
            </ButtonItem>
            <ButtonItem
                layout="below"
                onClick={checkForUpdates}
            >
                {"Check For Updates"}
            </ButtonItem>
            <ButtonItem
                layout="below"
                onClick={updateAll}
            >
                {"Update All"}
            </ButtonItem>
            <PanelSection>
                {addonList.map(function (object) {
                     return AddonInfo(object, newVersions);
                }) || "Loading..."}
            </PanelSection>
        </PanelSectionRow>
    </PanelSection>);
}

function Title() {
    const [pluginVersion, setPluginVersion] = useState<string>("");
    const onLoad = async () => {
        const version = await get_version();
        setPluginVersion(version);
    }
    onLoad();
    return (<div className={staticClasses.Title}>WoW Addon Updater {pluginVersion || "Loading..."}</div>)
}

export default definePlugin(() => {
    console.log("Template plugin initializing, this is called once on frontend startup")
    start_scheduler()

    // Add an event listener to the "timer_event" event from the backend
    const listener = addEventListener<[new_versions: number]>("new_versions_found", (new_versions) => {
        toaster.toast({
            title: "New versions found: ", body: "New versions: " +  new_versions,
        });
    });


    return {
        // The name shown in various decky menus
        name: "WoW Addon Updater", // The element displayed at the top of your plugin's menu
        titleView: <Title/>, // The title of your plugin's menu'content of your plugin's menu
        content: <Content/>, // The icon displayed in the plugin list
        icon: <FaShip/>, // The function triggered when your plugin unloads
        onDismount() {
            console.log("Unloading")
            removeEventListener("new_versions_found", listener);
            // serverApi.routerHook.removeRoute("/decky-plugin-test");
        },
    };
});
