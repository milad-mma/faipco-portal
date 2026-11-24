// Must match backend/app/core/android_assetlinks.py and Android APK flavors.
export const PRODUCTION_PACKAGE = "ir.faipco.portal";
export const STAGING_PACKAGE = "ir.faipco.portal.test";
export const STAGING_HOST = "portal-test.faipco.ir";

export function androidIdentityForHost(hostname = "") {
  const host = String(hostname).toLowerCase().replace(/\.+$/, "");
  return host === STAGING_HOST
    ? { packageName: STAGING_PACKAGE, scheme: "faipco-test" }
    : { packageName: PRODUCTION_PACKAGE, scheme: "faipco" };
}

export function isExpectedAndroidReferrer(referrer, packageName) {
  try {
    const url = new URL(referrer);
    // Exact package match: the production package is a prefix of staging.
    return url.protocol === "android-app:" && url.host === packageName &&
      !url.username && !url.password;
  } catch {
    return false;
  }
}
