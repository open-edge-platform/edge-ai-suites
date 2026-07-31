// Re-export the OpenClaw plugin SDK surface this plugin uses.
// `openclaw` is provided by the gateway at load time, not a repo dependency.
export {
  definePluginEntry,
  type OpenClawPluginApi,
} from "openclaw/plugin-sdk/plugin-entry";
