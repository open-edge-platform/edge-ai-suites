// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

/**
 * Turning what the model wrote into something jsMind will render.
 *
 * The mind map is LLM output stored verbatim (result/mindmap.mmd), so it is
 * *nearly* a jsMind node_tree and not reliably one: code fences, a key typed as
 * `topic：` with a full-width colon, a missing id, the same id twice. Every
 * repair here exists because a real session produced that file and jsMind threw
 * on it.
 *
 * Shared by the live mind-map tab and the history's file preview: they read the
 * same bytes, one from the summarizer's reply and one from disk, and must
 * tolerate the same mistakes.
 */

/** Thrown by cleanJsMindContent when nothing recognizable could be recovered. */
export const INVALID_FORMAT = 'INVALID_FORMAT';

const sanitizeNode = (node: any, fallbackIndex: number = 0, seen = new Set<string>()): any => {
  if (!node || typeof node !== 'object' || Array.isArray(node)) return null;

  // Recover id from typo keys like "id:", "id：", " id", "Id"
  let id = node.id;
  if (!id || typeof id !== 'string') {
    const candidateKeys = Object.keys(node).filter(
      k => /^[\s]*id[\s:：.]*$/i.test(k) && k !== 'id'
    );
    const candidate = candidateKeys.length ? node[candidateKeys[0]] : null;
    id = (candidate && typeof candidate === 'string') ? candidate : `node_${fallbackIndex}_${Date.now()}`;
  }
  id = id.trim();

  // Deduplicate ids — jsMind requires unique ids across the tree
  if (seen.has(id)) {
    id = `${id}_dup_${fallbackIndex}`;
  }
  seen.add(id);

  // Recover topic from typo keys like "topic:", "Topic", "label", "text", "name"
  let topic = node.topic;
  if (!topic || typeof topic !== 'string') {
    const topicAliases = Object.keys(node).find(
      k => /^[\s]*(topic[\s:：.]*|label|text|title|name)[\s]*$/i.test(k) && k !== 'topic'
    );
    const candidate = topicAliases ? node[topicAliases] : null;
    topic = (candidate && typeof candidate === 'string') ? candidate : id;
  }
  topic = topic.trim() || id;

  // Truncate excessively long topics that break rendering
  if (topic.length > 200) {
    topic = topic.slice(0, 197) + '...';
  }

  const sanitized: any = { id, topic };

  // Preserve direction if present (left/right for jsMind layout)
  if (node.direction && typeof node.direction === 'string') {
    sanitized.direction = node.direction;
  }

  // Recover children from typo keys like "children:", "child", "nodes", "sub"
  let children = node.children;
  if (!Array.isArray(children)) {
    const childAliases = Object.keys(node).find(
      k => /^[\s]*(children[\s:：.]*|child|nodes|sub|subtopics)[\s]*$/i.test(k) && k !== 'children'
    );
    children = childAliases ? node[childAliases] : undefined;
  }

  if (Array.isArray(children)) {
    sanitized.children = children
      .map((child: any, i: number) => sanitizeNode(child, i, seen))
      .filter(Boolean);
  }

  return sanitized;
};

const validateJsMindData = (data: any): boolean => {
  try {
    if (!data || typeof data !== 'object') return false;
    if (!data.meta || !data.format || !data.data) return false;
    if (data.format !== 'node_tree') return false;
    if (!data.data.id || !data.data.topic) return false;
    data.data = sanitizeNode(data.data);
    return true;
  } catch {
    return false;
  }
};

/** Extracts the first balanced {...} block from a string. */
const extractFirstJsonObject = (text: string): string | null => {
  const start = text.indexOf("{");
  if (start === -1) return null;
  let depth = 0;
  let inString = false;
  let escape = false;
  for (let i = start; i < text.length; i++) {
    const ch = text[i];
    if (escape) { escape = false; continue; }
    if (ch === "\\" && inString) { escape = true; continue; }
    if (ch === '"') { inString = !inString; continue; }
    if (inString) continue;
    if (ch === "{") depth++;
    else if (ch === "}") {
      depth--;
      if (depth === 0) return text.slice(start, i + 1);
    }
  }
  return null;
};

const tryParse = (s: string): any | null => {
  try {
    const p = JSON.parse(s);
    if (validateJsMindData(p)) return p;
  } catch { /* not this strategy's problem; the next one may recover it */ }
  return null;
};

/**
 * A jsMind node_tree recovered from raw model output.
 *
 * Empty input yields a placeholder root rather than an error — a mind map that
 * has not been written yet is not a broken one. Throws `INVALID_FORMAT` when
 * there is content but no tree in it, which callers render as their own notice.
 */
export const cleanJsMindContent = (content: string): any => {
  if (!content || !content.trim()) {
    return {
      "meta": { "name": "default", "author": "ai_assistant", "version": "1.0" },
      "format": "node_tree",
      "data": { "id": "root", "topic": "Main Topic", "children": [] }
    };
  }

  // Strategy 1: direct parse (handles clean JSON returned by backend)
  let result = tryParse(content.trim());
  if (result) return result;

  // Strategy 2: strip code fences then direct parse
  const stripped = content.replace(/```[a-zA-Z]*\n?([\s\S]*?)```/gs, "$1").trim();
  result = tryParse(stripped);
  if (result) return result;

  // Strategy 3: balanced-brace extractor on stripped content
  const extracted1 = extractFirstJsonObject(stripped);
  if (extracted1) {
    result = tryParse(extracted1);
    if (result) return result;
  }

  // Strategy 4: balanced-brace extractor on raw content (fallback if fence-strip corrupted it)
  const extracted2 = extractFirstJsonObject(content);
  if (extracted2) {
    result = tryParse(extracted2);
    if (result) return result;
  }

  console.error("cleanJsMindContent: all strategies failed. Raw content preview:", content.slice(0, 200));
  throw new Error(INVALID_FORMAT);
};
