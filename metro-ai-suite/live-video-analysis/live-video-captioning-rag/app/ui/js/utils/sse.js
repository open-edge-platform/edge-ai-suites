/**
 * SSE utilities (strict parser + text extract)
 */
const SSEUtil = (function () {
    const PUNCTUATION = new Set([',', '.', '!', '?', ':', ';', ')', ']', '}', '”', '’']);

    /*
     * Determines if a space should be inserted between two text chunks
     */
    function shouldInsertSpace(prev, next) {
        if (!prev || !next) return false;
        const last = prev[prev.length - 1];
        const first = next[0];
        if (/\s/.test(last)) return false;
        if (/\s/.test(first)) return false;
        if (PUNCTUATION.has(first)) return false;
        return true;
    }

    /*
     * Creates a strict SSE reader that only emits complete events with 'event:' and 'data:' lines
     */
    function createStrictSSEReader(onEvent) {
        let buffer = '';
        return {
            feed(chunk) {
                buffer += chunk;
                const frames = buffer.split(/\r?\n\r?\n/);
                buffer = frames.pop();

                for (const frame of frames) {
                    let eventName = 'message';
                    const dataLines = [];
                    for (const line of frame.split(/\r?\n/)) {
                        if (line.startsWith('event:')) {
                            eventName = line.slice(6).trim() || 'message';
                        } else if (line.startsWith('data:')) {
                            dataLines.push(line.slice(5)); // keep leading spaces
                        }
                    }
                    onEvent({ event: eventName, data: dataLines.join('\n') });
                }
            },
            flush() {
                if (buffer.trim()) onEvent({ event: 'message', data: buffer });
                buffer = '';
            }
        };
    }

    /*
     * Extracts text content from an SSE data payload, handling JSON structures if present
     */
    function extractText(payload) {
        if (!payload) return '';
        const trimmed = payload.trimStart();
        if (trimmed.startsWith('{')) {
            try {
                const obj = JSON.parse(trimmed);
                if (typeof obj === 'string') return obj;
                if (typeof obj?.content === 'string') return obj.content;
                if (typeof obj?.delta === 'string') return obj.delta;
                if (typeof obj?.token === 'string') return obj.token;
                if (Array.isArray(obj?.tokens)) return obj.tokens.join('');
                if (Array.isArray(obj?.deltas)) return obj.deltas.join('');
            } catch {
                // not JSON
            }
        }
        return payload;
    }

    return {
        createStrictSSEReader,
        extractText,
        shouldInsertSpace,
        PUNCTUATION
    };
})();