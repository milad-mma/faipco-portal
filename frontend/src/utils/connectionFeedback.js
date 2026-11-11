/** Connectivity diagnosis for the shared global banner. A failed /api/health
 * when the browser has networking is not proof the user's internet is down.
 */
export function connectionBannerKind({ isOnline, isBrowserOffline, updating }) {
  if (isOnline || updating) return null;
  return isBrowserOffline ? 'internet' : 'server';
}

export function connectionBannerDelay(kind) {
  if (kind === 'internet') return 2500;
  if (kind === 'server') return 6000;
  return 0;
}
