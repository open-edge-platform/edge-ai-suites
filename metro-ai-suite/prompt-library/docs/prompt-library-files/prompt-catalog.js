// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
//
// Dynamically loads the Metro Prompt Library prompts from the YAML files in the
// prompts/ directory, renders one tile per prompt (name + description), and
// opens an overlay with the full prompt text and Copy / Close actions.

(function () {
    "use strict";

    function ready(fn) {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", fn);
        } else {
            fn();
        }
    }

    // Minimal YAML reader for the prompt schema (name, description, prompt).
    function parsePromptYaml(text) {
        var lines = text.replace(/\r\n/g, "\n").split("\n");
        var data = {};
        var i = 0;

        function indentOf(line) {
            return line.length - line.replace(/^\s+/, "").length;
        }

        while (i < lines.length) {
            var line = lines[i];
            if (!line.trim() || /^\s*#/.test(line)) {
                i++;
                continue;
            }
            var match = line.match(/^([A-Za-z0-9_-]+):(.*)$/);
            if (!match || indentOf(line) !== 0) {
                i++;
                continue;
            }
            var key = match[1];
            var rest = match[2].trim();

            if (/^[|>][+-]?$/.test(rest)) {
                // Block scalar: literal (|) keeps newlines, folded (>) joins lines.
                var folded = rest.charAt(0) === ">";
                i++;
                var block = [];
                var baseIndent = null;
                while (i < lines.length) {
                    var l = lines[i];
                    if (l.trim() === "") {
                        block.push("");
                        i++;
                        continue;
                    }
                    if (indentOf(l) === 0) {
                        break;
                    }
                    if (baseIndent === null) {
                        baseIndent = indentOf(l);
                    }
                    block.push(l.slice(baseIndent));
                    i++;
                }
                while (block.length && block[block.length - 1] === "") {
                    block.pop();
                }
                if (folded) {
                    var value = "";
                    for (var k = 0; k < block.length; k++) {
                        if (block[k] === "") {
                            value += "\n";
                        } else {
                            value += (value && !/\n$/.test(value) ? " " : "") + block[k];
                        }
                    }
                    data[key] = value.trim();
                } else {
                    data[key] = block.join("\n");
                }
            } else if (rest === "") {
                // Nested block or list (e.g. tags) that we don't need — skip it.
                i++;
                while (i < lines.length && lines[i].trim() !== "" && indentOf(lines[i]) !== 0) {
                    i++;
                }
            } else {
                data[key] = rest.replace(/^["']|["']$/g, "");
                i++;
            }
        }
        return data;
    }

    function titleFromName(name) {
        return String(name || "")
            .split("-")
            .filter(Boolean)
            .map(function (w) {
                return w.charAt(0).toUpperCase() + w.slice(1);
            })
            .join(" ");
    }

    function buildOverlay() {
        var overlay = document.createElement("div");
        overlay.className = "prompt-overlay";
        overlay.setAttribute("hidden", "");
        overlay.setAttribute("role", "dialog");
        overlay.setAttribute("aria-modal", "true");
        overlay.innerHTML =
            '<div class="prompt-modal">' +
            '  <div class="prompt-modal-header">' +
            '    <h3 class="prompt-modal-title"></h3>' +
            "  </div>" +
            '  <div class="prompt-modal-body"><pre class="prompt-modal-text"></pre></div>' +
            '  <div class="prompt-modal-footer">' +
            '    <button type="button" class="prompt-btn prompt-btn-copy">Copy</button>' +
            '    <button type="button" class="prompt-btn prompt-btn-close">Close</button>' +
            "  </div>" +
            "</div>";
        document.body.appendChild(overlay);

        var titleEl = overlay.querySelector(".prompt-modal-title");
        var textEl = overlay.querySelector(".prompt-modal-text");
        var copyBtn = overlay.querySelector(".prompt-btn-copy");
        var closeBtn = overlay.querySelector(".prompt-btn-close");

        function close() {
            overlay.setAttribute("hidden", "");
            copyBtn.textContent = "Copy";
        }

        function open(title, text) {
            titleEl.textContent = title;
            textEl.textContent = text;
            copyBtn.textContent = "Copy";
            overlay.removeAttribute("hidden");
            closeBtn.focus();
        }

        copyBtn.addEventListener("click", function () {
            var text = textEl.textContent;
            var done = function () {
                copyBtn.textContent = "Copied!";
            };
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).then(done, function () {
                    fallbackCopy(text);
                    done();
                });
            } else {
                fallbackCopy(text);
                done();
            }
        });

        function fallbackCopy(text) {
            var ta = document.createElement("textarea");
            ta.value = text;
            ta.style.position = "fixed";
            ta.style.opacity = "0";
            document.body.appendChild(ta);
            ta.select();
            try {
                document.execCommand("copy");
            } catch (e) {
                /* ignore */
            }
            document.body.removeChild(ta);
        }

        closeBtn.addEventListener("click", close);
        overlay.addEventListener("click", function (e) {
            if (e.target === overlay) {
                close();
            }
        });
        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape" && !overlay.hasAttribute("hidden")) {
                close();
            }
        });

        return { open: open };
    }

    ready(function () {
        var root = document.getElementById("prompt-catalog");
        if (!root) {
            return;
        }

        var list = (root.getAttribute("data-prompts") || "")
            .split(",")
            .map(function (s) {
                return s.trim();
            })
            .filter(Boolean);

        var basePath = root.getAttribute("data-prompts-path") || "prompts/";
        if (basePath.charAt(basePath.length - 1) !== "/") {
            basePath += "/";
        }

        if (!list.length) {
            root.innerHTML = '<p class="prompt-catalog-error">No prompts configured.</p>';
            return;
        }

        var overlay = buildOverlay();

        Promise.all(
            list.map(function (nameSlug) {
                return fetch(basePath + nameSlug + ".yaml")
                    .then(function (res) {
                        if (!res.ok) {
                            throw new Error("HTTP " + res.status);
                        }
                        return res.text();
                    })
                    .then(function (text) {
                        var parsed = parsePromptYaml(text);
                        return {
                            slug: nameSlug,
                            title: titleFromName(parsed.name || nameSlug),
                            description: parsed.description || "",
                            prompt: parsed.prompt || ""
                        };
                    })
                    .catch(function () {
                        return null;
                    });
            })
        ).then(function (items) {
            var prompts = items.filter(Boolean);
            if (!prompts.length) {
                root.innerHTML =
                    '<p class="prompt-catalog-error">Unable to load prompts.</p>';
                return;
            }
            root.innerHTML = "";
            prompts.forEach(function (item) {
                var card = document.createElement("button");
                card.type = "button";
                card.className = "prompt-card";
                var h3 = document.createElement("h3");
                h3.textContent = item.title;
                var desc = document.createElement("p");
                desc.className = "prompt-card-desc";
                desc.textContent = item.description;
                var cta = document.createElement("span");
                cta.className = "prompt-card-cta";
                cta.textContent = "View prompt →";
                card.appendChild(h3);
                card.appendChild(desc);
                card.appendChild(cta);
                card.addEventListener("click", function () {
                    overlay.open(item.title, item.prompt);
                });
                root.appendChild(card);
            });
        });
    });
})();
