import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, existsSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { preserveAssetLinks, isValidAssetLinks } from '../scripts/preserveAssetLinks.mjs';

const fp = Array(32).fill('AB').join(':');
const valid = JSON.stringify([{
  relation: ['delegate_permission/common.handle_all_urls'],
  target: { namespace: 'android_app', package_name: 'ir.faipco.portal', sha256_cert_fingerprints: [fp] },
}]);
const example = valid.replace(fp, 'REPLACE_WITH_REAL_SHA256_FINGERPRINT_AFTER_RUNNING_BUBBLEWRAP');

function setup(initial) {
  const root = mkdtempSync(join(tmpdir(), 'faipco-assetlinks-'));
  const dir = join(root, 'dist', '.well-known');
  mkdirSync(dir, { recursive: true });
  const file = join(dir, 'assetlinks.json');
  if (initial !== undefined) writeFileSync(file, initial);
  const plugin = preserveAssetLinks();
  plugin.configResolved({ root, build: { outDir: 'dist' }, logger: { warn() {} } });
  return { root, dir, file, plugin, cleanup() { rmSync(root, { recursive: true, force: true }); } };
}

test('only valid fingerprints for our Android package are accepted', () => {
  assert.equal(isValidAssetLinks(valid), true);
  assert.equal(isValidAssetLinks(example), false);
  assert.equal(isValidAssetLinks('not json'), false);
  assert.equal(isValidAssetLinks(valid.replace('ir.faipco.portal', 'different.package')), false);
});

test('a direct Vite build restores the verified file after dist is cleaned', () => {
  const s = setup(valid);
  try {
    rmSync(join(s.root, 'dist'), { recursive: true });
    s.plugin.writeBundle.call({ warn() {}, error(msg) { throw Error(msg); } });
    assert.equal(readFileSync(s.file, 'utf8'), valid);
  } finally { s.cleanup(); }
});

test('a newer FastAPI-generated valid fingerprint is never overwritten', () => {
  const s = setup(valid);
  try {
    const newer = valid.replace(fp, Array(32).fill('CD').join(':'));
    writeFileSync(s.file, newer);
    s.plugin.writeBundle.call({ warn() {}, error(msg) { throw Error(msg); } });
    assert.equal(readFileSync(s.file, 'utf8'), newer);
  } finally { s.cleanup(); }
});

test('placeholder is not preserved when dist is rebuilt', () => {
  const s = setup(example);
  try {
    rmSync(join(s.root, 'dist'), { recursive: true });
    s.plugin.writeBundle.call({ warn() {}, error(msg) { throw Error(msg); } });
    assert.equal(existsSync(s.file), false);
  } finally { s.cleanup(); }
});

test('fresh installs do not create fake association data', () => {
  const s = setup();
  try {
    s.plugin.writeBundle.call({ warn() {}, error(msg) { throw Error(msg); } });
    assert.equal(existsSync(s.file), false);
  } finally { s.cleanup(); }
});
