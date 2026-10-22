// Runs the browser runtime under node on the real P5R.exe and checks its output is byte-identical
// to tools/p5r_patch.py (same sets as web/app/patches.js).
// usage: node web/test/parity.mjs [original/P5R.exe]
import fs from 'node:fs';
import { execFileSync } from 'node:child_process';
import crypto from 'node:crypto';
import vm from 'node:vm';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const app = path.join(here, '..', 'app');
const exe = process.argv[2] || path.join(here, '..', '..', 'original', 'P5R.exe');
const g = globalThis;
for (const f of ['patches.js', 'patcher-runtime.js']) vm.runInThisContext(fs.readFileSync(path.join(app, f), 'utf8'));
const T = g.P5R_PATCHES;

const file = await fs.openAsBlob(exe);
file.name = 'P5R.exe';
const res = await g.P5R43.patch(file);
if (!res.ok) { console.error(res.reason, res.log, res.failures); process.exit(1); }
const out = Buffer.from(await res.output.arrayBuffer());
const sha = crypto.createHash('sha256').update(out).digest('hex');
const tmp = '/tmp/p5r-parity.exe';
execFileSync('python3', ['-I', path.join(here, '..', '..', 'tools', 'p5r_patch.py'), exe, tmp, '--set', T.sets.join(',')], { stdio: 'pipe' });
const ref = crypto.createHash('sha256').update(fs.readFileSync(tmp)).digest('hex');
fs.unlinkSync(tmp);
console.log('js   ', sha, '(runtime reported', res.outputSha256 + ')');
console.log('python', ref);
if (sha !== ref || res.outputSha256 !== ref) { console.error('MISMATCH'); process.exit(1); }
if (res.inputSha256 !== T.sha256) { console.error('input hash mismatch'); process.exit(1); }
// negative: an already patched file must be recognised
const f2 = new Blob([out]); f2.name = 'P5R.exe';
const r2 = await g.P5R43.patch(f2);
if (r2.reason !== 'already_patched') { console.error('expected already_patched, got', r2.reason); process.exit(1); }
console.log('parity OK, already_patched OK');
