/**
 * Preserve the verified Android Digital Asset Links file across Vite rebuilds.
 *
 * The authoritative SHA-256 is configured in the admin panel and written by
 * FastAPI to dist/.well-known/assetlinks.json. Do not ship a public/ placeholder:
 * Vite would otherwise overwrite the real file on every build.
 */
import { existsSync, mkdirSync, readFileSync, renameSync, statSync, writeFileSync, chownSync, unlinkSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';

const EXPECTED_PACKAGE = 'ir.faipco.portal';
const FINGERPRINT = /^([0-9A-Fa-f]{2}:){31}[0-9A-Fa-f]{2}$/;

export function isValidAssetLinks(raw) {
  try {
    const data = JSON.parse(raw);
    return Array.isArray(data) && data.some(entry =>
      entry?.relation?.includes('delegate_permission/common.handle_all_urls') &&
      entry?.target?.namespace === 'android_app' &&
      entry.target.package_name === EXPECTED_PACKAGE &&
      Array.isArray(entry.target.sha256_cert_fingerprints) &&
      entry.target.sha256_cert_fingerprints.some(fp => typeof fp === 'string' && FINGERPRINT.test(fp))
    );
  } catch {
    return false;
  }
}

export function preserveAssetLinks({ root = process.cwd(), outDir = 'dist' } = {}) {
  let saved = null;
  let outputPath;
  return {
    name: 'faipco-preserve-android-assetlinks',
    apply: 'build',
    configResolved(config) {
      outputPath = join(resolve(config.root || root, config.build.outDir || outDir), '.well-known', 'assetlinks.json');
      if (existsSync(outputPath)) {
        const raw = readFileSync(outputPath, 'utf8');
        if (isValidAssetLinks(raw)) {
          saved = { raw, stat: statSync(outputPath) };
        } else {
          config.logger.warn('[assetlinks] Existing file is invalid; not preserving an example or malformed file.');
        }
      }
    },
    writeBundle() {
      if (!saved) return; // On a fresh installation, FastAPI generates this after startup.
      // If FastAPI has regenerated the file during the build, prefer that
      // newer verified value instead of restoring the fingerprint from start.
      if (existsSync(outputPath) && isValidAssetLinks(readFileSync(outputPath, 'utf8'))) return;
      const dir = dirname(outputPath);
      mkdirSync(dir, { recursive: true });
      const temporary = `${outputPath}.build-${process.pid}.tmp`;
      try {
        writeFileSync(temporary, saved.raw, { encoding: 'utf8', mode: saved.stat.mode & 0o777 });
        // When the deployment runs as root, retain www-data ownership so the
        // backend can update the fingerprint when settings are saved later.
        try {
          chownSync(temporary, saved.stat.uid, saved.stat.gid);
        } catch (err) {
          if (saved.stat.uid !== process.getuid?.()) {
            this.warn(`[assetlinks] Could not restore original file ownership: ${err.message}`);
          }
        }
        renameSync(temporary, outputPath);
      } finally {
        if (existsSync(temporary)) unlinkSync(temporary);
      }
      if (!isValidAssetLinks(readFileSync(outputPath, 'utf8'))) {
        this.error('[assetlinks] Build failed to preserve valid Android Digital Asset Links.');
      }
    },
  };
}
