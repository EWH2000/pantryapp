/* Barcode scan-to-add.
 *
 * The camera decode is the one place HTMX can't reach (it can't run a video
 * decode loop), so this is the app's hand-written vanilla JS. Flow:
 *   tap Scan -> open the camera overlay -> decode a UPC/EAN in the browser ->
 *   send just the number to GET /scan/lookup -> pre-fill the add form (new item)
 *   or offer "+1" on the item we already own (dedup). No image ever leaves the
 *   device; only the number does.
 *
 * Decoder: native BarcodeDetector when present (Android Chrome) is the fast
 * path; vendored ZXing is the fallback AND the primary path on iOS Safari,
 * which has no BarcodeDetector. We manage getUserMedia ourselves so camera
 * failures (insecure context / denied / no camera) degrade cleanly to the
 * always-present "Use a photo" still-frame fallback.
 */
(function () {
    "use strict";

    // Single source of truth for URLs — scan.js can't read Jinja's base_path,
    // so base.html hands it over on <body data-base-path>. Behind the hub proxy
    // this is "/pantry"; in dev it's "". Never hardcode "/scan/..." below.
    var BASE = (document.body && document.body.dataset.basePath) || "";

    var btn = document.getElementById("scan-btn");
    if (!btn) return;                       // not on a page with the scanner

    var overlay = document.getElementById("scan-overlay");
    var video = document.getElementById("scan-video");
    var hint = document.getElementById("scan-hint");
    var fileInput = document.getElementById("scan-file");
    var cancelBtn = document.getElementById("scan-cancel");
    var resultBox = document.getElementById("scan-result");

    // --- lifecycle state (for clean camera teardown) -----------------------
    var stream = null;          // the live MediaStream, so we can stop its tracks
    var zxingReader = null;     // active ZXing reader (its reset() stops decoding)
    var rafId = 0;              // requestAnimationFrame id for the native loop
    var scanning = false;       // true while the overlay is open and decoding
    var handled = false;        // guards against the continuous loop firing twice
    var detectorPromise = null; // cached BarcodeDetector (async to build)

    var hasNative = ("BarcodeDetector" in window);

    // ZXing formats we care about — grocery codes are EAN-13 / UPC-A (+ the
    // shorter EAN-8 / UPC-E). Restricting formats keeps the decode fast.
    function zxingHints() {
        var hints = new Map();
        hints.set(ZXing.DecodeHintType.POSSIBLE_FORMATS, [
            ZXing.BarcodeFormat.EAN_13, ZXing.BarcodeFormat.UPC_A,
            ZXing.BarcodeFormat.EAN_8, ZXing.BarcodeFormat.UPC_E
        ]);
        hints.set(ZXing.DecodeHintType.TRY_HARDER, true);
        return hints;
    }

    function ensureDetector() {
        if (!detectorPromise) {
            detectorPromise = (async function () {
                var want = ["ean_13", "upc_a", "ean_8", "upc_e"];
                var formats = want;
                try {
                    var sup = await window.BarcodeDetector.getSupportedFormats();
                    formats = want.filter(function (f) { return sup.indexOf(f) !== -1; });
                    if (!formats.length) formats = null;
                } catch (e) { /* getSupportedFormats unsupported → detect all */ }
                return formats
                    ? new window.BarcodeDetector({ formats: formats })
                    : new window.BarcodeDetector();
            })();
        }
        return detectorPromise;
    }

    // --- opening the scanner ----------------------------------------------
    async function openScanner() {
        if (resultBox) resultBox.hidden = true;
        overlay.hidden = false;
        overlay.setAttribute("aria-hidden", "false");
        overlay.classList.remove("is-fallback");
        hint.textContent = "Point the camera at a barcode";
        scanning = true;
        handled = false;

        if (!hasNative && typeof ZXing === "undefined") {
            fallback("Scanner library didn't load. Tap “Use a photo” or Cancel.");
            return;
        }
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            fallback("Live camera needs a secure (HTTPS) connection. Tap “Use a photo”.");
            return;
        }

        // ideal (not exact) so a front-camera-only device still opens.
        var constraints = { video: { facingMode: { ideal: "environment" } }, audio: false };
        try {
            stream = await navigator.mediaDevices.getUserMedia(constraints);
        } catch (err) {
            var name = err && err.name;
            var msg = "Couldn’t open the camera. Tap “Use a photo”.";
            if (name === "NotAllowedError" || name === "SecurityError")
                msg = "Camera blocked — allow it, or the page isn’t HTTPS. Tap “Use a photo”.";
            else if (name === "NotFoundError" || name === "OverconstrainedError")
                msg = "No camera found. Tap “Use a photo”.";
            fallback(msg);
            return;
        }

        if (hasNative) {
            try { await startNative(); return; }
            catch (e) { /* fall through to ZXing */ }
        }
        try { await startZxing(); }
        catch (e) { fallback("Couldn’t start the scanner. Tap “Use a photo”."); }
    }

    async function startNative() {
        var detector = await ensureDetector();
        video.srcObject = stream;
        await video.play();
        nativeLoop(detector);
    }

    async function nativeLoop(detector) {
        if (!scanning) return;
        try {
            var codes = await detector.detect(video);
            if (codes && codes.length && codes[0].rawValue) {
                onDecode(codes[0].rawValue);
                return;
            }
        } catch (e) { /* transient detect error — keep scanning */ }
        if (scanning) rafId = requestAnimationFrame(function () { nativeLoop(detector); });
    }

    async function startZxing() {
        zxingReader = new ZXing.BrowserMultiFormatReader(zxingHints());
        // Continuous decode straight off the stream we already hold; the reader
        // attaches it to <video>, plays, and calls back on each frame.
        await zxingReader.decodeFromStream(stream, video, function (result, err) {
            if (!scanning) return;
            if (result) onDecode(result.getText());
            // err is a NotFoundException between frames — normal, ignore it.
        });
    }

    // --- still-photo fallback ---------------------------------------------
    // Drop the live video and lean on the file input (works on plain HTTP).
    function fallback(message) {
        overlay.classList.add("is-fallback");
        hint.textContent = message;
        stopStreamOnly();
    }

    async function onFilePicked(e) {
        var file = e.target.files && e.target.files[0];
        e.target.value = "";                // let the same file be re-picked
        if (!file) return;
        hint.textContent = "Reading photo…";
        var code = await decodeFile(file);
        if (code) {
            handled = false;
            onDecode(code);
        } else {
            hint.textContent = "Couldn’t read a barcode in that photo. Try again, or Cancel and type it.";
        }
    }

    async function decodeFile(file) {
        if (hasNative) {
            try {
                var detector = await ensureDetector();
                var bitmap = await createImageBitmap(file);
                var codes = await detector.detect(bitmap);
                if (bitmap.close) bitmap.close();
                if (codes && codes.length && codes[0].rawValue) return codes[0].rawValue;
                return null;
            } catch (e) { return null; }
        }
        var url = URL.createObjectURL(file);
        var reader = new ZXing.BrowserMultiFormatReader(zxingHints());
        try {
            var result = await reader.decodeFromImageUrl(url);
            return result ? result.getText() : null;
        } catch (e) {
            return null;                    // NotFoundException = no code in image
        } finally {
            try { reader.reset(); } catch (e2) {}
            URL.revokeObjectURL(url);
        }
    }

    // --- on a successful decode -------------------------------------------
    async function onDecode(raw) {
        if (handled) return;                // continuous loop can fire twice
        handled = true;
        scanning = false;
        var code = (raw || "").replace(/\D/g, "");   // keep digits; let OFF normalize
        stopScanner();                      // close overlay + release the camera
        if (code.length < 8) {
            showText("That didn’t look like a product barcode. Try again.");
            return;
        }
        await runLookup(code);
    }

    async function runLookup(code) {
        showText("Looking up " + code + "…");
        var data = null;
        try {
            var resp = await fetch(
                BASE + "/scan/lookup?barcode=" + encodeURIComponent(code),
                { headers: { "Accept": "application/json" } }
            );
            if (resp.ok) data = await resp.json();
        } catch (e) { data = null; }

        var barcodeField = document.getElementById("add-barcode");
        var nameField = document.querySelector("#add-form [name=name]");
        var qtyField = document.querySelector("#add-form [name=quantity]");

        // Already in the pantry → offer +1, don't pre-fill a duplicate.
        if (data && data.existing) {
            if (barcodeField) barcodeField.value = "";
            showExisting(data.existing);
            return;
        }

        if (barcodeField) barcodeField.value = code;   // store it on whatever we add
        if (data && data.product) {
            if (nameField) nameField.value = data.product.name;
            // Pack count parsed from the name/size ("6 pack", "24 x 355 ml") —
            // a better default than 1 for multipacks. Editable like any field.
            if (qtyField && data.product.count) qtyField.value = data.product.count;
            showFilled(data.product);
            if (qtyField) { qtyField.focus(); if (qtyField.select) qtyField.select(); }
        } else if (data) {
            if (nameField) { nameField.value = ""; nameField.focus(); }
            showText("Barcode " + code + " saved — type a name, then Add.");
        } else {
            if (nameField) { nameField.value = ""; nameField.focus(); }
            showText("Lookup failed — barcode " + code + " saved. Type a name, then Add.");
        }
    }

    // --- the feedback banner under the add form ---------------------------
    function showText(msg) {
        resultBox.innerHTML = "";
        var span = document.createElement("span");
        span.className = "scan-result__text";
        span.textContent = msg;            // textContent: never inject product text as HTML
        resultBox.appendChild(span);
        resultBox.hidden = false;
    }

    function showFilled(product) {
        var bits = [];
        if (product.brands) bits.push(product.brands);
        if (product.package_size) bits.push(product.package_size);
        var detail = bits.length ? " (" + bits.join(" · ") + ")" : "";
        var tail = product.count
            ? ". Quantity set to " + product.count + " from the pack — adjust if needed, then Add."
            : ". Set quantity & where, then Add.";
        showText("Filled from barcode: " + product.name + detail + tail);
    }

    function showExisting(existing) {
        resultBox.innerHTML = "";
        var span = document.createElement("span");
        span.className = "scan-result__text";
        span.appendChild(document.createTextNode("Already in your pantry: "));
        var b = document.createElement("b");
        b.textContent = existing.name;
        span.appendChild(b);
        span.appendChild(document.createTextNode(
            " (" + formatQty(existing.quantity) + "). Bought more?"));

        var bump = document.createElement("button");
        bump.type = "button";
        bump.className = "btn scan-bump";
        bump.textContent = "+1";
        bump.addEventListener("click", function () {
            bumpItem(existing.id);
            resultBox.hidden = true;
        });

        var dismiss = document.createElement("button");
        dismiss.type = "button";
        dismiss.className = "scan-dismiss";
        dismiss.textContent = "Dismiss";
        dismiss.addEventListener("click", function () { resultBox.hidden = true; });

        resultBox.appendChild(span);
        resultBox.appendChild(bump);
        resultBox.appendChild(dismiss);
        resultBox.hidden = false;
    }

    function bumpItem(id) {
        var url = BASE + "/items/" + id + "/bump";
        // Reuse HTMX's swap so the list refresh matches every other mutation.
        if (window.htmx) {
            window.htmx.ajax("POST", url, { target: "#item-list", swap: "innerHTML" });
            return;
        }
        fetch(url, { method: "POST" })
            .then(function (r) { return r.text(); })
            .then(function (html) {
                var list = document.getElementById("item-list");
                if (list) list.innerHTML = html;
            });
    }

    function formatQty(q) {
        // Match the template's "%g": drop a trailing ".0" but keep real decimals.
        return (typeof q === "number") ? String(q) : ("" + q);
    }

    // --- teardown ----------------------------------------------------------
    function stopStreamOnly() {
        if (rafId) { cancelAnimationFrame(rafId); rafId = 0; }
        if (zxingReader) { try { zxingReader.reset(); } catch (e) {} zxingReader = null; }
        if (stream) {
            stream.getTracks().forEach(function (t) { t.stop(); });
            stream = null;
        }
        if (video) video.srcObject = null;
    }

    function stopScanner() {
        scanning = false;
        stopStreamOnly();
        overlay.hidden = true;
        overlay.setAttribute("aria-hidden", "true");
        overlay.classList.remove("is-fallback");
    }

    // --- wiring ------------------------------------------------------------
    btn.addEventListener("click", openScanner);
    cancelBtn.addEventListener("click", stopScanner);
    fileInput.addEventListener("change", onFilePicked);
    // Don't keep the camera running if the user backgrounds the tab/app.
    document.addEventListener("visibilitychange", function () {
        if (document.hidden && scanning) stopScanner();
    });
})();
