// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// Single source of truth for every filesystem location the Electron service
// manager touches. Nothing else in electron/services/ may build paths by hand.

const fs = require('fs');
const path = require('path');

// ui/electron/services -> ui/electron -> ui -> smart-classroom
const BUNDLED_HOME = path.resolve(__dirname, '..', '..', '..');

function isSmartClassroomHome(dir) {
  return !!dir && fs.existsSync(path.join(dir, 'main.py')) && fs.existsSync(path.join(dir, 'config.yaml'));
}

// Packaged builds sit outside the source tree, so allow an explicit override.
function home() {
  const override = process.env.SMART_CLASSROOM_HOME;
  if (isSmartClassroomHome(override)) return path.resolve(override);
  return BUNDLED_HOME;
}

const isWindows = process.platform === 'win32';

// The backend venv is a sibling of smart-classroom (education-ai-suite/smartclassroom)
function venvDir() {
  return path.join(path.dirname(home()), 'smartclassroom');
}

function venvPython(dir = venvDir()) {
  return isWindows ? path.join(dir, 'Scripts', 'python.exe') : path.join(dir, 'bin', 'python');
}

function layoutServiceDir() {
  return path.join(home(), 'components', 'grading', 'providers', 'layout_detection_service');
}

const paths = {
  isWindows,
  home,
  venvDir,
  venvPython,
  layoutServiceDir,
  configFile: () => path.join(home(), 'config.yaml'),
  runtimeConfigFile: () => path.join(home(), 'runtime_config.yaml'),
  proxyConfigFile: () => path.join(home(), '.proxy-config'),
  requirementsFile: () => path.join(home(), 'requirements.txt'),
  dlStreamerScript: () => path.join(home(), 'Scripts', 'check_dlstreamer.ps1'),
  convertVenvDir: () => path.join(layoutServiceDir(), 'venv_convert'),
  convertRequirementsFile: () => path.join(layoutServiceDir(), 'requirements_convert.txt'),
  layoutIrModel: () => path.join(home(), 'models', 'detection_model', 'PP-DocLayoutV2-ov', 'fp16', 'model.xml'),
  // Logs captured by the manager itself; distinct from the app's own
  // monitoring/logs and monitoring/executionlogs trees.
  managerLogDir: () => path.join(home(), 'logs', 'manager'),
  configBackupDir: () => path.join(home(), 'logs', 'config-backups'),
};

module.exports = paths;
