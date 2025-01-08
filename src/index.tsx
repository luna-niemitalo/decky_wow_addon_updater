import {
    ButtonItem, PanelSection, PanelSectionRow, Focusable, //Navigation,
    staticClasses
} from "@decky/ui";
import {
    addEventListener, removeEventListener, callable, definePlugin, toaster, // routerHook
} from "@decky/api"
import {useEffect, useState} from "react";
import {FaShip} from "react-icons/fa";

// import logo from "../assets/logo.png";

// This function calls the python function "add", which takes in two numbers and returns their sum (as a number)
// Note the type annotations:
//  the first one: [first: number, second: number] is for the arguments
//  the second one: number is for the return value
//const add = callable<[first: number, second: number], number>("add");

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

const check_for_updates = callable<[], IAddonVersionInfo[]>("check_for_updates");
const get_addons_with_updates = callable<[], IAddonVersionInfo[]>("get_addons_with_updates");

// This function calls the python function "start_timer", which takes in no arguments and returns nothing.

// It starts a (python) timer which eventually emits the event 'timer_event'
const startTimer = callable<[], void>("start_timer");
const stop_long_running = callable<[], void>("stop_long_running");

const timers: NodeJS.Timeout[] = [];
interface IAddonStatus {
    updateLoopRunning: boolean; // Add a new field to represent the status
}

function get_updates(info: IAddonInfo, versions: IAddonVersionInfo[]) {
    return info.current_version_id + "->" +  versions.filter(v => v.version_id > info.current_version_id && v.project_id === info.project_id).map(v => v.version_id).join(', ');
}

function AddonInfo(info: IAddonInfo, versions: IAddonVersionInfo[]): JSX.Element {
    return (
        <Focusable>
            <h2>{info.name}</h2>
            <p>Project ID: {info.project_id}</p>
            <p>Desired Version: {info.desired_version}</p>
            <p>Date: {info.date}</p>
            <p>Current Version ID: {info.current_version_id}</p>
            <p>Available Updates:</p>
            <ul>
                {get_updates(info, versions)}
            </ul>
        </Focusable>
)
    ;
}

function Content() {
    const [addonList, setAddonList] = useState<IAddonInfo[]>([]);
    const [newVersions, setnewVersions] = useState<IAddonVersionInfo[]>([]);
    const [addonStatus, setAddonStatus] = useState<IAddonStatus>({updateLoopRunning: false});

    const onAddonList = async () => {
        const result = await list_addons();
        setAddonList(result);
    };
    onAddonList();

    const checkForUpdates = async () => {
        const result = await check_for_updates();
        setnewVersions(result);
    };
    const getUpdatesFromDB = async () => {
        const result = await get_addons_with_updates();
        setnewVersions(result);
    };
    const getUpdateLoopStatus = async () => {
        const status = await callable<[], boolean>("get_update_loop_status")();
        setAddonStatus({ updateLoopRunning: status });
    };

    const availableUpdates: any[] = [];

    useEffect(() => {
        getUpdateLoopStatus();
        get_addons_with_updates().then(r => availableUpdates.push(...r));
    }, []);


    return (<PanelSection title="Panel Section">
        <PanelSectionRow>
            <ButtonItem
                layout="below"
                onClick={() => startTimer()}
            >
                {"Start Python timer"}
            </ButtonItem>
        </PanelSectionRow>
        <PanelSectionRow>
            Update Loop Status: {addonStatus.updateLoopRunning ? "Running" : "Not Running"}
            Available updates: {newVersions.length }
        </PanelSectionRow>
        <PanelSectionRow>
            <ButtonItem
                layout="below"
                onClick={() => stop_long_running()}
            >
                {"Stop Python timer"}
            </ButtonItem>
        </PanelSectionRow>
        <PanelSectionRow>
            <ButtonItem
                layout="below"
                onClick={getUpdatesFromDB}
            >
                {"Get Updates from DB"}
            </ButtonItem>
            <ButtonItem
                layout="below"
                onClick={checkForUpdates}
            >
                {"Check For Updates"}
            </ButtonItem>

            <PanelSection>
                {addonList.map(function (object) {
                     return AddonInfo(object, newVersions);
                }) || "Loading..."}
            </PanelSection>
            <PanelSection>
                {newVersions.map(function (object, i) {
                    return <PanelSectionRow key={i}>{object["version_id"]} </PanelSectionRow>;
                }) || "Loading..."}
            </PanelSection>
        </PanelSectionRow>

        {/* <PanelSectionRow>
        <div style={{ display: "flex", justifyContent: "center" }}>
          <img src={logo} />
        </div>
      </PanelSectionRow> */}

        {/*<PanelSectionRow>
        <ButtonItem
          layout="below"
          onClick={() => {
            Navigation.Navigate("/decky-plugin-test");
            Navigation.CloseSideMenus();
          }}
        >
          Router
        </ButtonItem>
      </PanelSectionRow>*/}
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


    // serverApi.routerHook.addRoute("/decky-plugin-test", DeckyPluginRouterTest, {
    //   exact: true,
    // });

    // Add an event listener to the "timer_event" event from the backend
    const listener = addEventListener<[test1: string, test2: boolean, test3: number]>("timer_event", (test1, test2, test3) => {
        console.log("Template got timer_event with:", test1, test2, test3)
        toaster.toast({
            title: "template got timer_event", body: `${test1}, ${test2}, ${test3}`
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
            timers.forEach(clearInterval);
            removeEventListener("timer_event", listener);
            // serverApi.routerHook.removeRoute("/decky-plugin-test");
        },
    };
});
