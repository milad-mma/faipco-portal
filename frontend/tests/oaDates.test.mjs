import assert from 'node:assert/strict';
import { test } from 'node:test';
import { spawnSync } from 'node:child_process';
import { oaJalaliEndOfDay, oaToJalali } from '../src/utils/oaDates.js';

test('office automation stores due dates at the end of the Tehran day', () => {
  assert.equal(oaJalaliEndOfDay('1405/08/20'), '2026-11-11T20:29:00.000Z');
  assert.equal(oaToJalali('2026-11-11T20:29:00.000Z'), '1405/08/20');
  assert.equal(oaJalaliEndOfDay('bad'), null);
});

test('Tehran due date does not depend on Android/desktop timezone', () => {
  const code = 'import { oaJalaliEndOfDay, oaToJalali } from "./src/utils/oaDates.js"; process.stdout.write(JSON.stringify([oaJalaliEndOfDay("1405/08/20"), oaToJalali("2026-11-11T20:29:00.000Z")]));';
  const results = ['UTC', 'Asia/Tehran', 'America/New_York', 'Pacific/Honolulu'].map((TZ) => {
    const run = spawnSync(process.execPath, ['--input-type=module', '-e', code], {
      cwd: new URL('..', import.meta.url).pathname, env: { ...process.env, TZ }, encoding: 'utf8',
    });
    assert.equal(run.status, 0, run.stderr);
    return run.stdout;
  });
  assert.equal(new Set(results).size, 1);
});
