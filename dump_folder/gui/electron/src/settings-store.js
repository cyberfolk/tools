const fs = require("fs");
const path = require("path");

function getSettingsPath(app) {
  return path.join(app.getPath("userData"), "dump_builder_electron_settings.json");
}

function loadSettings(app) {
  const settingsPath = getSettingsPath(app);
  try {
    if (!fs.existsSync(settingsPath)) {
      return {};
    }
    return JSON.parse(fs.readFileSync(settingsPath, "utf8"));
  } catch {
    return {};
  }
}

function saveSettings(app, partialSettings, options = {}) {
  const current = options.merge ? loadSettings(app) : {};
  const next = { ...current, ...partialSettings };
  const settingsPath = getSettingsPath(app);
  fs.mkdirSync(path.dirname(settingsPath), { recursive: true });
  fs.writeFileSync(settingsPath, JSON.stringify(next, null, 2), "utf8");
}

module.exports = {
  loadSettings,
  saveSettings,
};
