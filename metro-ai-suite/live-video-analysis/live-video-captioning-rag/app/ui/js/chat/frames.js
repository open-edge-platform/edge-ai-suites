/**
 * Inline frame rendering for bot bubbles
 */
const FrameRenderer = (function () {

    /*
     * Determines if a space should be inserted between two text chunks
     */
    function isDataURL(str) {
        return typeof str === 'string' && str.startsWith('data:');
    }

    /*
     * Naively sniffs common image MIME types from base64 prefixes
     */
    function sniffImageMimeFromBase64(b64) {
        if (!b64) return null;
        if (b64.startsWith('/9j/')) return 'image/jpeg';
        if (b64.startsWith('iVBORw0KGgo')) return 'image/png';
        if (b64.startsWith('UklG')) return 'image/webp';
        return null;
    }

    /*
     * Converts a BGRA base64 frame to a data URL
     */
    async function bgraBase64ToDataURL(frameB64, w, h) {
        const binary = atob(frameB64);
        const len = binary.length;
        const buf = new Uint8ClampedArray(len);
        for (let i = 0; i < len; i++) buf[i] = binary.charCodeAt(i);
        // BGRA → RGBA
        for (let i = 0; i < len; i += 4) {
            const b = buf[i], g = buf[i + 1], r = buf[i + 2], a = buf[i + 3];
            buf[i] = r; buf[i + 1] = g; buf[i + 2] = b; buf[i + 3] = a;
        }
        const canvas = document.createElement('canvas');
        canvas.width = w; canvas.height = h;
        const ctx = canvas.getContext('2d');
        ctx.putImageData(new ImageData(buf, w, h), 0, 0);
        return canvas.toDataURL('image/png');
    }

    /*
     * Builds an inline frame element from frame data
     */
    async function buildInlineFrame(frame) {
        const { metadata = {}, preview = '' } = frame || {};
        const { frame_data: raw = '', frame_format: fmt, frame_width: w, frame_height: h } = metadata;

        const wrap = document.createElement('div');
        wrap.className = 'inline-frame';

        const img = document.createElement('img');
        img.className = 'inline-frame-img';
        img.alt = preview || 'Frame';

        try {
            if (isDataURL(raw)) {
                img.src = raw;
            } else {
                const sniffed = sniffImageMimeFromBase64(raw);
                if (sniffed) {
                    img.src = `data:${sniffed};base64,${raw}`;
                } else if ((fmt || '').toUpperCase() === 'BGRA' && Number.isFinite(w) && Number.isFinite(h)) {
                    img.src = await bgraBase64ToDataURL(raw, w, h);
                } else {
                    img.src = `data:image/jpeg;base64,${raw}`;
                }
            }
        } catch (e) {
            console.error('inline frame build failed', e);
        }

        const cap = document.createElement('div');
        cap.className = 'inline-frame-cap';
        cap.textContent = preview || '';

        wrap.appendChild(img);
        wrap.appendChild(cap);
        return wrap;
    }

    /*
     * Determines if a space should be inserted between two text chunks
     */
    async function renderFramesInsideBubble(botBubbleEl, frames) {
        if (!botBubbleEl || !frames) return;

        if (typeof frames === 'string') {
            try { frames = JSON.parse(frames); } catch { return; }
        }
        if (!Array.isArray(frames) || frames.length === 0) return;

        let gallery = botBubbleEl.querySelector('.inline-frame-gallery');
        if (!gallery) {
            gallery = document.createElement('div');
            gallery.className = 'inline-frame-gallery';
            botBubbleEl.appendChild(gallery);
        }

        for (const f of frames) {
            const node = await buildInlineFrame(f);
            gallery.appendChild(node);
        }

        const meta = botBubbleEl.querySelector('.msg-meta');
        if (meta) botBubbleEl.appendChild(meta);
    }

    return {
        renderFramesInsideBubble
    };
})();