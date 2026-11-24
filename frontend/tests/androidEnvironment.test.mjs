import test from 'node:test';
import assert from 'node:assert/strict';
import { androidIdentityForHost, isExpectedAndroidReferrer } from '../src/utils/androidEnvironment.js';

const production = { packageName: 'ir.faipco.portal', scheme: 'faipco' };
const staging = { packageName: 'ir.faipco.portal.test', scheme: 'faipco-test' };

test('production retains its original package and native scheme', () => {
  assert.deepEqual(androidIdentityForHost('portal.faipco.ir'), production);
});

test('staging uses the test package and native scheme', () => {
  assert.deepEqual(androidIdentityForHost('portal-test.faipco.ir'), staging);
  assert.deepEqual(androidIdentityForHost('PORTAL-TEST.FAIPCO.IR.'), staging);
});

test('the staging hostname must match exactly', () => {
  assert.deepEqual(androidIdentityForHost('portal-test.faipco.ir.example.com'), production);
  assert.deepEqual(androidIdentityForHost('localhost'), production);
});

test('production and staging referrers are not interchangeable', () => {
  assert.equal(isExpectedAndroidReferrer('android-app://ir.faipco.portal', production.packageName), true);
  assert.equal(isExpectedAndroidReferrer('android-app://ir.faipco.portal.test/', staging.packageName), true);
  assert.equal(isExpectedAndroidReferrer('android-app://ir.faipco.portal.test', production.packageName), false);
  assert.equal(isExpectedAndroidReferrer('android-app://ir.faipco.portal', staging.packageName), false);
  assert.equal(isExpectedAndroidReferrer('android-app://ir.faipco.portal.attacker', production.packageName), false);
  assert.equal(isExpectedAndroidReferrer('https://ir.faipco.portal', production.packageName), false);
  assert.equal(isExpectedAndroidReferrer('', production.packageName), false);
  assert.equal(isExpectedAndroidReferrer('android-app://user@ir.faipco.portal', production.packageName), false);
});

for (const [host, identity] of [['portal.faipco.ir', production], ['portal-test.faipco.ir', staging]]) {
  test(`native setup and portal links target the correct package for ${host}`, async () => {
    const savedWindow = globalThis.window;
    try {
      globalThis.window = { location: { hostname: host, host, origin: `https://${host}`, pathname: '/profile', search: '', href: '' } };
      const module = await import(`../src/utils/androidApp.js?environment=${host}`);
      module.openNativeSetup();
      assert.ok(window.location.href.includes(`;scheme=${identity.scheme};package=${identity.packageName};`));
      module.openNativePairing('test-code');
      assert.ok(window.location.href.includes(`;scheme=${identity.scheme};package=${identity.packageName};`));
      module.openPortalInApp('/notices');
      assert.ok(window.location.href.startsWith(`intent://${host}/notices#Intent;scheme=https;package=${identity.packageName};`));
    } finally {
      if (savedWindow === undefined) delete globalThis.window;
      else globalThis.window = savedWindow;
    }
  });
}
