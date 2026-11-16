/**
 * Brand-derived values used by runtime documentation and code samples.
 *
 * The deployment brand (site_name) is editable in /admin/settings, so examples
 * must not hard-code the default product name. Keep the generated environment
 * prefix stable and shell/Python/TypeScript friendly; non-Latin brand names
 * fall back to a neutral prefix.
 */
export function brandEnvPrefix(siteName?: string | null): string {
  const token = (siteName || '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
  return token || 'DECISIONS'
}

/** Origin of the current deployment, used instead of a fictional example domain. */
export function deploymentOrigin(): string {
  if (typeof window === 'undefined') return 'https://example.com'
  return window.location.origin
}
