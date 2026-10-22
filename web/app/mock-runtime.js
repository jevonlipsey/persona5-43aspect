/* DEV ONLY - fake P5R43 runtime that implements the real contract with delays.
 * Loaded by main.js only when the URL has ?mock. Always overrides any existing P5R43.
 *
 * Choose the outcome with a query param:   ?mock=ok | already_patched | not_p5r | verify_failed | error | loadfail
 * Otherwise (plain ?mock) it is picked from the chosen file name (case-insensitive):
 *   "patched" -> already_patched, "notchef" -> not_p5r, "bad" or "fail" -> verify_failed,
 *   "error" -> error, anything else -> ok.
 * Extra knobs:  ?loadms=3000 (runtime load time)  ?patchms=4000 (patch time)  ?version=5.7.0-mock
 */
(function () {
  'use strict';
  var q = new URLSearchParams(location.search);
  var forced = q.get('mock');
  var LOAD_MS = +(q.get('loadms') || 2500);
  var PATCH_MS = +(q.get('patchms') || 3000);
  var VERSION = q.get('version') || 'v5.7-mock';
  var TOTAL = 1048576;
  var loadP = null;

  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  function hex(buf) {
    return Array.prototype.map.call(new Uint8Array(buf), function (b) { return ('0' + b.toString(16)).slice(-2); }).join('');
  }
  function sha256(bytes) {
    if (globalThis.crypto && crypto.subtle) return crypto.subtle.digest('SHA-256', bytes).then(hex);
    var s = ''; for (var i = 0; i < 64; i++) s += ((bytes[i % bytes.length] || 0) + i * 7 & 15).toString(16);
    return Promise.resolve(s);
  }

  function pick(bytes, name) {
    if (forced === 'ok') return 'ok';
    if (forced) return forced;
    var n = (name || '').toLowerCase();
    if (n.indexOf('patched') >= 0) return 'already_patched';
    if (n.indexOf('notchef') >= 0) return 'not_p5r';
    if (n.indexOf('bad') >= 0 || n.indexOf('fail') >= 0) return 'verify_failed';
    if (n.indexOf('error') >= 0) return 'error';
    return 'ok';
  }

  var P5R43 = {
    version: undefined,   // real runtime may leave this unset; version arrives with patch()

    load: function (onProgress) {
      if (loadP) return loadP;
      loadP = (async function () {
        if (forced === 'loadfail') {
          if (onProgress) onProgress({ loaded: 0, total: TOTAL, label: 'Downloading runtime' });
          await sleep(800);
          throw new Error('mock: WebAssembly instantiate failed (simulated)');
        }
        var steps = 25;
        for (var i = 0; i <= steps; i++) {
          if (onProgress) {
            if (i < 3) onProgress({ label: 'Starting' });                         // label-only call
            else onProgress({ loaded: Math.round(TOTAL * i / steps), total: TOTAL, label: i === steps ? 'Initializing' : 'Downloading' });
          }
          await sleep(LOAD_MS / steps);
        }
      })();
      return loadP;
    },

    patch: async function (file) {
      var bytes = new Uint8Array(await file.slice(0, 4096).arrayBuffer());
      var name = file.name || '';
      // main.js hands us only bytes, so fall back to the picked file name in the <input>.
      try { var inp = document.getElementById('file'); if (inp && inp.files && inp.files[0]) name = inp.files[0].name; } catch (e) { /* ignore */ }
      var reason = pick(bytes, name);
      await sleep(PATCH_MS);
      var inSha = await sha256(bytes);
      var base = { ok: false, reason: reason, output: null, log: '', passed: 0, failed: 0, skipped: 0, failures: [], inputSha256: inSha, outputSha256: null, version: VERSION };
      var log = ['[mock] patcher ' + VERSION, '[mock] input ' + file.size + ' bytes', '[mock] sha256 ' + inSha];

      if (reason === 'ok') {
        var out = new Blob([file, 'mock'], { type: 'application/octet-stream' });
        base.ok = true; base.output = out; base.outputSha256 = inSha.split('').reverse().join('');
        base.passed = 7; base.skipped = 0;
        for (var i = 0; i < 12; i++) log.push('[mock] patched method #' + i);
        log.push('[mock] verify: 7 passed');
      } else if (reason === 'already_patched') {
        log.push('[mock] marker type P5R43 found: already patched');
      } else if (reason === 'not_p5r') {
        log.push('[mock] type SettingsPanel not found: not Persona 5 Royal');
      } else if (reason === 'verify_failed') {
        base.passed = 5; base.failed = 2;
        base.failures = [
          'fit h=1a1a02 @1a0a02: found 0f1f4400, expected f30f59d4',
          'cam site @1b0d2e: found 90909090, expected f30f114374'
        ];
        log.push('[mock] verify: 5 passed, 2 failed');
        base.failures.forEach(function (f) { log.push('FAIL ' + f); });
      } else {
        base.reason = 'error';
        log.push('[mock] System.NullReferenceException: Object reference not set to an instance of an object.');
        log.push('   at P5R43.Patcher.Run(Byte[] input)');
      }
      base.log = log.join('\n');
      return base;
    }
  };

  globalThis.P5R43 = P5R43;
})();
