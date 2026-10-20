// Turns the body of GET /api/v1/health into a short label for the page.
// Kept as a pure function so it can be unit tested without a browser.
export function describeHealth(body: unknown): string {
  if (typeof body === 'object' && body !== null && 'status' in body && body.status === 'ok') {
    return 'API is up'
  }
  return 'API returned an unexpected response'
}
