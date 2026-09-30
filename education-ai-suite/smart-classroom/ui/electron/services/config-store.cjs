// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// Read and write access to the app's on-disk configuration: config.yaml and
// .proxy-config.
//
// Writes go through config-schema.cjs, which allowlists the editable paths, and
// edit the parsed YAML *document* rather than re-serialising a plain object, so
// the extensive inline comments in config.yaml survive.

const fs = require('fs');
const path = require('path');
const YAML = require('yaml');
const paths = require('./paths.cjs');
const schema = require('./config-schema.cjs');

const MAX_BACKUPS = 10;
const SECRET_PLACEHOLDER = '__UNCHANGED__';

const cache = new Map(); // file -> { mtimeMs, value }

function readYaml(file) {
  let stat;
  try {
    stat = fs.statSync(file);
  } catch {
    return {};
  }
  const hit = cache.get(file);
  if (hit && hit.mtimeMs === stat.mtimeMs) return hit.value;
  let value = {};
  try {
    value = YAML.parse(fs.readFileSync(file, 'utf8')) || {};
  } catch {
    // Malformed YAML: surface as "no config" so gating falls back to defaults
    // rather than crashing the manager.
    value = {};
  }
  cache.set(file, { mtimeMs: stat.mtimeMs, value });
  return value;
}

function readConfig() {
  return readYaml(paths.configFile());
}

function featureEnabled(name, fallback = true) {
  const feature = readConfig()?.features?.[name];
  if (!feature || typeof feature.enabled !== 'boolean') return fallback;
  return feature.enabled;
}

function readProxyConfig() {
  try {
    const raw = JSON.parse(fs.readFileSync(paths.proxyConfigFile(), 'utf8'));
    return {
      httpProxy: raw.httpProxy || '',
      httpsProxy: raw.httpsProxy || '',
      noProxy: raw.noProxy || '',
    };
  } catch {
    return { httpProxy: '', httpsProxy: '', noProxy: '' };
  }
}

// Proxy vars injected into every child process, mirroring what the PowerShell
// scripts export into their child terminals (both cases, as pip/requests differ).
function proxyEnv() {
  const { httpProxy, httpsProxy, noProxy } = readProxyConfig();
  const env = {};
  if (httpProxy) {
    env.http_proxy = httpProxy;
    env.HTTP_PROXY = httpProxy;
  }
  if (httpsProxy) {
    env.https_proxy = httpsProxy;
    env.HTTPS_PROXY = httpsProxy;
  }
  if (noProxy) {
    env.no_proxy = noProxy;
    env.NO_PROXY = noProxy;
  }
  return env;
}

module.exports = {
  readConfig,
  featureEnabled,
  readProxyConfig,
  proxyEnv,
  describe,
  validate,
  apply,
  SECRET_PLACEHOLDER,
  invalidate: () => cache.clear(),
};

// ---------------------------------------------------------------------------
// Settings editor
// ---------------------------------------------------------------------------

function fileFor(id) {
  if (id === schema.CONFIG) return paths.configFile();
  if (id === schema.PROXY) return paths.proxyConfigFile();
  throw new Error(`Unknown config file: ${id}`);
}

function valueAt(source, dottedPath) {
  return dottedPath.split('.').reduce((node, key) => (node == null ? undefined : node[key]), source);
}

/** Schema plus current values, with secrets replaced by a set/not-set marker. */
function describe() {
  const sources = {
    [schema.CONFIG]: readConfig(),
    [schema.PROXY]: readProxyConfig(),
  };

  const fields = schema.FIELDS.map((field) => {
    const raw = valueAt(sources[field.file], field.path);
    return {
      path: field.path,
      file: field.file,
      group: field.group,
      subgroup: field.subgroup ?? null,
      label: field.label,
      type: field.type,
      options: field.options ?? null,
      suggestions: field.suggestions ?? null,
      wizard: !!field.wizard,
      help: field.help ?? null,
      min: field.min ?? null,
      max: field.max ?? null,
      // The token itself never crosses the IPC boundary.
      value: field.type === 'secret' ? null : normaliseForUi(field, raw),
      isSet: field.type === 'secret' ? isSecretSet(raw) : undefined,
    };
  });

  return { groups: schema.GROUPS, subgroups: schema.SUBGROUPS, fields };
}

function isSecretSet(raw) {
  if (typeof raw !== 'string') return false;
  const trimmed = raw.trim();
  return trimmed !== '' && trimmed.toLowerCase() !== 'none' && trimmed.toLowerCase() !== 'null';
}

// config.yaml uses YAML's permissive booleans ("False", "True") in places, so
// normalise before handing values to typed form controls.
function normaliseForUi(field, raw) {
  if (raw === undefined || raw === null) return field.type === 'boolean' ? false : '';
  if (field.type === 'boolean') {
    if (typeof raw === 'boolean') return raw;
    return String(raw).toLowerCase() === 'true';
  }
  if (field.type === 'number') return typeof raw === 'number' ? raw : Number(raw);
  return String(raw);
}

/** Type/range check every change and group it by file. */
function prepare(changes) {
  if (!Array.isArray(changes)) throw new Error('No changes supplied.');
  if (changes.length > 100) throw new Error('Too many changes in one request.');

  const byFile = new Map();
  for (const change of changes) {
    const field = schema.get(change?.file, change?.path);
    if (!field) throw new Error(`Setting is not editable: ${String(change?.path).slice(0, 80)}`);
    // An untouched secret comes back as a placeholder; leave the stored value
    // alone. It still counts as "set" once merged, because the merge starts
    // from what is on disk.
    if (field.type === 'secret' && change.value === SECRET_PLACEHOLDER) continue;

    const value = schema.coerce(field, change.value);
    if (!byFile.has(field.file)) byFile.set(field.file, []);
    byFile.get(field.file).push({ path: field.path, value });
  }
  return byFile;
}

function setAt(target, dottedPath, value) {
  const keys = dottedPath.split('.');
  let node = target;
  for (const key of keys.slice(0, -1)) {
    if (typeof node[key] !== 'object' || node[key] === null) node[key] = {};
    node = node[key];
  }
  node[keys[keys.length - 1]] = value;
}

/**
 * asr_handle.py::_ensure_diarization_model treats the model as cached when
 * config.yaml is present in the directory ensure_model.get_diarization_model_path()
 * computes.
 */
function diarizationModelReady(cfg) {
  const diarization = cfg?.models?.diarization;
  const base = diarization?.models_base_path;
  const provider = diarization?.provider;
  const name = diarization?.name;
  if (!base || !provider || !name) return false;
  const dir = path.resolve(
    paths.home(),
    String(base),
    String(provider),
    String(name).split('/').join('_')
  );
  try {
    return fs.existsSync(path.join(dir, 'config.yaml'));
  } catch {
    return false;
  }
}

/**
 * Cross-field problems `changes` would leave behind. Rules read the whole
 * resulting document, not just the edits.
 *
 * A problem is `blocking` only when the edit introduces it or edits a field it
 * names. config.yaml is also hand-editable, and the PowerShell setup script
 * writes it too, so the file can already be in a state these rules dislike;
 * refusing every save then would strand the user, unable to change an unrelated
 * setting until they fixed something they never touched. Those are still
 * returned, for the screen to show as a warning.
 *
 * An `advisory` rule is never blocking however it arose: the backend accepts
 * that config and works around it, so refusing the save would be this screen
 * inventing a restriction the backend does not have.
 *
 * @returns {Array<{file: string, path: string, rule: string, message: string, blocking: boolean}>}
 */
function problemsFor(byFile) {
  const current = readConfig();
  // structuredClone, because readConfig() hands back the cached object.
  const next = structuredClone(current);
  const entries = byFile.get(schema.CONFIG) ?? [];
  for (const { path: dotted, value } of entries) setAt(next, dotted, value);

  const check = (cfg) => schema.validate(cfg, { diarizationModelReady: diarizationModelReady(cfg) });
  const after = check(next);
  if (!after.length) return [];

  const before = new Set(check(current).map((problem) => problem.rule));
  const edited = new Set(entries.map((entry) => entry.path));
  // Whole-rule, not per-path: editing the provider must also flag the model
  // name it now contradicts, or the message would point at a field the screen
  // is not highlighting.
  const editedRules = new Set(after.filter((problem) => edited.has(problem.path)).map((problem) => problem.rule));

  // `advisory` is consumed here rather than sent on: the renderer decides what
  // to show from `blocking`, and a second severity flag beside it would only
  // invite the two to disagree.
  return after.map(({ advisory, ...problem }) => ({
    ...problem,
    blocking: !advisory && (!before.has(problem.rule) || editedRules.has(problem.rule)),
  }));
}

/** Dry run: what saving `changes` would be rejected for. Writes nothing. */
function validate(changes) {
  return problemsFor(prepare(changes ?? []));
}

/**
 * Validate and persist a batch of changes.
 * @param {Array<{path: string, file: string, value: unknown}>} changes
 * @returns {{written: string[], skipped: number}}
 */
function apply(changes) {
  if (!Array.isArray(changes) || changes.length === 0) throw new Error('No changes supplied.');

  const byFile = prepare(changes);

  // Checked here and not only in the renderer: this is the security boundary,
  // and the screen is not the only caller.
  const problems = problemsFor(byFile).filter((problem) => problem.blocking);
  if (problems.length) {
    // One message per rule; the same message is repeated for each field it flags.
    const unique = [...new Set(problems.map((problem) => problem.message))];
    const error = new Error(unique.join(' '));
    error.problems = problems;
    throw error;
  }

  const written = [];
  for (const [fileId, entries] of byFile) {
    if (fileId === schema.PROXY) writeProxy(entries);
    else writeYaml(fileFor(fileId), entries);
    written.push(fileId);
  }

  cache.clear();
  return { written, skipped: changes.length - [...byFile.values()].flat().length };
}

function writeYaml(file, entries) {
  const existing = fs.existsSync(file) ? fs.readFileSync(file, 'utf8') : '';
  const doc = existing ? YAML.parseDocument(existing) : new YAML.Document({});
  if (doc.errors?.length) throw new Error(`${path.basename(file)} could not be parsed; fix it by hand first.`);

  let text = patchScalars(existing, doc, entries);
  backup(file);
  writeAtomic(file, text);
}

/**
 * Rewrite just the scalars named by `entries`, leaving every other byte of the
 * file alone.
 *
 * doc.toString() would re-emit the whole document, and the YAML parser keeps
 * only the text after a `#` — not the run of spaces before it. Round-tripping
 * config.yaml through it therefore collapses every aligned inline comment to a
 * single space, on lines nobody edited. Splicing the value into the original
 * text keeps the comment alignment, the quoting style, the blank lines and the
 * line endings exactly as the author wrote them.
 *
 * A key that is not already in the file has no range to splice, so those fall
 * back to setIn plus a full re-emit. That only happens if a key was deleted by
 * hand; every path in the schema ships in config.yaml.
 */
function patchScalars(text, doc, entries) {
  const edits = [];
  const missing = [];

  for (const { path: dotted, value } of entries) {
    const node = doc.getIn(dotted.split('.'), true);
    if (!node || !YAML.isScalar(node) || !node.range) {
      missing.push({ path: dotted, value });
      continue;
    }
    const [start, end, nodeEnd] = node.range;
    const replacement = scalarText(value, node);

    // When the comment is padded out to a column, absorb the value's change in
    // length into that padding so the `#` does not shift. Never below one space.
    const gap = /^([^\S\r\n]+)#/.exec(text.slice(end, nodeEnd));
    const padding = gap ? ' '.repeat(Math.max(1, gap[1].length - (replacement.length - (end - start)))) : '';
    edits.push({ start, end: end + (gap ? gap[1].length : 0), text: replacement + padding });
  }

  // Back to front: a splice must not invalidate the ranges still to be applied.
  edits.sort((a, b) => b.start - a.start);
  let out = text;
  for (const edit of edits) out = out.slice(0, edit.start) + edit.text + out.slice(edit.end);

  if (!missing.length) return out;

  const patched = YAML.parseDocument(out);
  for (const { path: dotted, value } of missing) patched.setIn(dotted.split('.'), value);
  return patched.toString();
}

/** One scalar, serialised the way the file already writes that key. */
function scalarText(value, node) {
  const quoted = node.type === 'QUOTE_DOUBLE' || node.type === 'QUOTE_SINGLE';
  const options = quoted && typeof value === 'string' ? { defaultStringType: node.type } : {};
  return YAML.stringify(value, { lineWidth: 0, ...options }).replace(/\n$/, '');
}

function writeProxy(entries) {
  const file = paths.proxyConfigFile();
  const current = readProxyConfig();
  for (const { path: key, value } of entries) current[key] = value;
  backup(file);
  writeAtomic(file, `${JSON.stringify(current, null, 2)}\n`);
}

// Temp file plus rename, so an interrupted write cannot leave a truncated
// config.yaml behind.
function writeAtomic(file, contents) {
  const temp = `${file}.tmp`;
  fs.writeFileSync(temp, contents, 'utf8');
  fs.renameSync(temp, file);
}

function backup(file) {
  if (!fs.existsSync(file)) return;
  try {
    const dir = paths.configBackupDir();
    fs.mkdirSync(dir, { recursive: true });
    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    fs.copyFileSync(file, path.join(dir, `${path.basename(file)}.${stamp}.bak`));

    const prefix = `${path.basename(file)}.`;
    const backups = fs
      .readdirSync(dir)
      .filter((name) => name.startsWith(prefix) && name.endsWith('.bak'))
      .sort();
    for (const name of backups.slice(0, Math.max(0, backups.length - MAX_BACKUPS))) {
      fs.rmSync(path.join(dir, name), { force: true });
    }
  } catch {
    // A missing backup must not block the edit itself.
  }
}
