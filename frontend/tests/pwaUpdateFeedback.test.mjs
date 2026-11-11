import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  UPDATE_TITLE, UPDATE_ACTION, UPDATE_ACTIVATING_TEXT,
  UPDATE_ACTIVATING_ACTION, UPDATE_RELOADING_TEXT, UPDATE_RELOADING_ACTION,
  UPDATE_RETRY_ACTION, updateReadyDescription, updateSuccessMessage, updateErrorMessage,
} from '../src/utils/updateFeedback.js';

test('release and cache refresh show the exact same user-approved prompt', () => {
  assert.equal(UPDATE_TITLE, 'سامانه آماده به روزرسانی است');
  assert.equal(UPDATE_ACTION, 'به روزرسانی');
  const expected = 'برای استفاده از آخرین نسخه پرتال، «به روزرسانی» را انتخاب کنید.';
  assert.equal(updateReadyDescription('release'), expected);
  assert.equal(updateReadyDescription('cache_refresh'), expected);
});

test('progress, reload and completion copies exactly match the approved messages', () => {
  assert.equal(UPDATE_ACTIVATING_TEXT, 'در حال آماده‌سازی و فعال‌کردن نسخه جدید...');
  assert.equal(UPDATE_ACTIVATING_ACTION, 'در حال به‌روزرسانی...');
  assert.equal(UPDATE_RELOADING_TEXT, 'سامانه به روزرسانی شد.');
  assert.equal(UPDATE_RELOADING_ACTION, 'در حال بارگذاری ...');
  assert.equal(updateSuccessMessage('release'), 'نسخه جدید سامانه با موفقیت بارگذاری شد.');
  assert.equal(updateSuccessMessage('cache_refresh'), 'سامانه با موفقیت بارگذاری شد.');
  assert.equal(UPDATE_RETRY_ACTION, 'تلاش دوباره');
});

test('retry messages exactly match the approved messages', () => {
  assert.equal(updateErrorMessage('not-ready'), 'فایل‌های به‌روزرسانی آماده نیستند. کمی بعد دوباره تلاش کنید.');
  assert.equal(updateErrorMessage('activation-timeout'), 'بارگذاری نسخه جدید طولانی شد. لطفا دوباره تلاش کنید.');
  assert.equal(updateErrorMessage('unsupported'), 'به‌روزرسانی خودکار در این مرورگر پشتیبانی نمی‌شود. صفحه را دوباره باز کنید.');
  assert.equal(updateErrorMessage('unexpected'), 'به‌روزرسانی انجام نشد. دوباره تلاش کنید.');
});

test('UpdatePrompt consumes the same shared copy without stale literal button labels', () => {
  const component = readFileSync(new URL('../src/components/UpdatePrompt.jsx', import.meta.url), 'utf8');
  for (const token of ['UPDATE_ACTION', 'UPDATE_ACTIVATING_TEXT', 'UPDATE_ACTIVATING_ACTION', 'UPDATE_RELOADING_TEXT', 'UPDATE_RELOADING_ACTION', 'UPDATE_RETRY_ACTION']) {
    assert.ok(component.includes(token), `missing copy token ${token}`);
  }
  assert.doesNotMatch(component, /: "بارگذاری"/);
});
