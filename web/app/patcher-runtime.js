/* Persona 5 Royal 4:3 patcher - browser runtime (pure JavaScript, no WebAssembly). Classic script
 * that needs patches.js first; defines globalThis.P5R43:
 *   P5R43.load(onProgress) -> Promise<void>      idempotent
 *   P5R43.patch(File) -> Promise<{ok, reason, output(Blob), log, passed, failed, skipped,
 *                                 failures, inputSha256, outputSha256, version}>
 * The 395 MB exe is never held in memory: it is read in 8 MB slices to hash and verify it, and the
 * download is a Blob stitched from slices of the original file plus the few patched byte runs.
 */
(function () {
  'use strict';

  var VERSION = 'v1.0';
  var CHUNK = 8 * 1048576;   // multiple of 64

  // ---- incremental SHA-256 ----
  var K = new Uint32Array([
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2]);

  function Sha256() {
    this.h = new Uint32Array([0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]);
    this.w = new Uint32Array(64);
    this.len = 0;
    this.tail = new Uint8Array(0);
  }
  Sha256.prototype.block = function (b, o) {
    var w = this.w, h = this.h, i;
    for (i = 0; i < 16; i++, o += 4) w[i] = (b[o] << 24) | (b[o + 1] << 16) | (b[o + 2] << 8) | b[o + 3];
    for (i = 16; i < 64; i++) {
      var a = w[i - 15], c = w[i - 2];
      var s0 = ((a >>> 7) | (a << 25)) ^ ((a >>> 18) | (a << 14)) ^ (a >>> 3);
      var s1 = ((c >>> 17) | (c << 15)) ^ ((c >>> 19) | (c << 13)) ^ (c >>> 10);
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) | 0;
    }
    var A = h[0], B = h[1], C = h[2], D = h[3], E = h[4], F = h[5], G = h[6], H = h[7];
    for (i = 0; i < 64; i++) {
      var S1 = ((E >>> 6) | (E << 26)) ^ ((E >>> 11) | (E << 21)) ^ ((E >>> 25) | (E << 7));
      var ch = (E & F) ^ (~E & G);
      var t1 = (H + S1 + ch + K[i] + w[i]) | 0;
      var S0 = ((A >>> 2) | (A << 30)) ^ ((A >>> 13) | (A << 19)) ^ ((A >>> 22) | (A << 10));
      var mj = (A & B) ^ (A & C) ^ (B & C);
      var t2 = (S0 + mj) | 0;
      H = G; G = F; F = E; E = (D + t1) | 0; D = C; C = B; B = A; A = (t1 + t2) | 0;
    }
    h[0] = (h[0] + A) | 0; h[1] = (h[1] + B) | 0; h[2] = (h[2] + C) | 0; h[3] = (h[3] + D) | 0;
    h[4] = (h[4] + E) | 0; h[5] = (h[5] + F) | 0; h[6] = (h[6] + G) | 0; h[7] = (h[7] + H) | 0;
  };
  Sha256.prototype.update = function (d) {
    this.len += d.length;
    var o = 0;
    if (this.tail.length) {
      var need = 64 - this.tail.length;
      if (d.length < need) { var t = new Uint8Array(this.tail.length + d.length); t.set(this.tail); t.set(d, this.tail.length); this.tail = t; return; }
      var blk = new Uint8Array(64); blk.set(this.tail); blk.set(d.subarray(0, need), this.tail.length);
      this.block(blk, 0); o = need; this.tail = new Uint8Array(0);
    }
    for (; o + 64 <= d.length; o += 64) this.block(d, o);
    if (o < d.length) this.tail = d.slice(o);
  };
  Sha256.prototype.hex = function () {
    var n = this.len, t = this.tail, pad = new Uint8Array(((t.length + 9 + 63) >> 6) << 6);
    pad.set(t); pad[t.length] = 0x80;
    var bits = n * 8, dv = new DataView(pad.buffer);
    dv.setUint32(pad.length - 8, Math.floor(bits / 4294967296)); dv.setUint32(pad.length - 4, bits >>> 0);
    for (var o = 0; o < pad.length; o += 64) this.block(pad, o);
    var s = '';
    for (var i = 0; i < 8; i++) s += ('00000000' + (this.h[i] >>> 0).toString(16)).slice(-8);
    return s;
  };

  function readSlice(file, a, b) {
    var s = file.slice(a, b);
    if (s.arrayBuffer) return s.arrayBuffer().then(function (x) { return new Uint8Array(x); });
    return new Promise(function (res, rej) {
      var r = new FileReader();
      r.onload = function () { res(new Uint8Array(r.result)); };
      r.onerror = function () { rej(r.error || new Error('Could not read the file.')); };
      r.readAsArrayBuffer(s);
    });
  }

  function unhex(h) { var o = new Uint8Array(h.length / 2); for (var i = 0; i < o.length; i++) o[i] = parseInt(h.substr(i * 2, 2), 16); return o; }
  function hex(b) { var s = ''; for (var i = 0; i < b.length; i++) s += ('0' + b[i].toString(16)).slice(-2); return s; }
  function yieldUi() { return new Promise(function (r) { setTimeout(r, 0); }); }

  var P5R43 = {
    version: VERSION,
    load: function (onProgress) {
      if (onProgress) onProgress({ label: 'Ready' });
      return Promise.resolve();
    },

    patch: async function (file) {
      var T = globalThis.P5R_PATCHES;
      var log = [];
      function out(reason, extra) {
        var r = { ok: false, reason: reason, output: null, log: log.join('\n'), passed: 0, failed: 0, skipped: 0,
          failures: [], inputSha256: '', outputSha256: null, version: VERSION };
        for (var k in extra) r[k] = extra[k];
        return r;
      }
      if (!T) throw new Error('patches.js is missing');
      log.push('P5R 4:3 patcher ' + VERSION + ', sets: ' + T.sets.join(', '));
      log.push('File: ' + file.name + ', ' + file.size + ' bytes');

      var head = await readSlice(file, 0, 2);
      if (head[0] !== 0x4d || head[1] !== 0x5a) return out('not_p5r', {});
      if (file.size !== T.size) {
        log.push('Size mismatch: expected ' + T.size);
        return out('verify_failed', { failures: ['file size is ' + file.size + ', this patcher expects ' + T.size + ' (Steam build of P5R.exe)'] });
      }

      var patches = T.patches.map(function (p) { return { name: p.name, offset: p.offset, old: unhex(p.old), nw: unhex(p.new) }; });
      var failures = [], already = 0;
      for (var i = 0; i < patches.length; i++) {
        var p = patches[i];
        var cur = await readSlice(file, p.offset, p.offset + p.old.length);
        var eqOld = hex(cur) === hex(p.old), eqNew = hex(cur) === hex(p.nw);
        if (eqNew) already++;
        else if (!eqOld) failures.push(p.name + ' @' + p.offset.toString(16) + ': found ' + hex(cur) + ', expected ' + hex(p.old));
      }
      if (already === patches.length) { log.push('Every patch is already present'); return out('already_patched', {}); }
      if (failures.length) {
        log.push('Byte checks failed');
        return out('verify_failed', { failures: failures, passed: patches.length - failures.length, failed: failures.length });
      }

      // one pass over the file: hash the input and the patched output together
      var hin = new Sha256(), hout = new Sha256();
      for (var off = 0; off < file.size; off += CHUNK) {
        var end = Math.min(off + CHUNK, file.size);
        var chunk = await readSlice(file, off, end);
        hin.update(chunk);
        var copy = null;
        for (var j = 0; j < patches.length; j++) {
          var q = patches[j], qe = q.offset + q.nw.length;
          if (q.offset < end && qe > off) {
            if (!copy) copy = chunk.slice();
            for (var k = Math.max(q.offset, off); k < Math.min(qe, end); k++) copy[k - off] = q.nw[k - q.offset];
          }
        }
        hout.update(copy || chunk);
        await yieldUi();
      }
      var inHex = hin.hex(), outHex = hout.hex();
      log.push('Input SHA-256  ' + inHex);
      log.push('Output SHA-256 ' + outHex);
      if (inHex !== T.sha256) log.push('Note: input hash differs from the tested build ' + T.sha256 + ' but every patch site matched.');

      var parts = [], pos = 0;
      patches.slice().sort(function (a, b) { return a.offset - b.offset; }).forEach(function (q) {
        if (q.offset > pos) parts.push(file.slice(pos, q.offset));
        parts.push(q.nw);
        pos = q.offset + q.nw.length;
      });
      parts.push(file.slice(pos, file.size));
      var blob = new Blob(parts, { type: 'application/octet-stream' });
      if (blob.size !== file.size) throw new Error('internal error: output size ' + blob.size);
      patches.forEach(function (q) { log.push('patched ' + q.name + ' @0x' + q.offset.toString(16)); });
      return {
        ok: true, reason: 'ok', output: blob, log: log.join('\n'), passed: patches.length, failed: 0, skipped: 0,
        failures: [], inputSha256: inHex, outputSha256: outHex, version: VERSION
      };
    }
  };

  globalThis.P5R43 = P5R43;
})();
