export const ANALYTICS_EVENTS = {
  WHATSAPP_CLICKED: 'whatsapp_clicked',
  CHECKOUT_FAILED: 'checkout_failed',
  RETRY_CLICKED: 'retry_clicked',
};

export function trackEvent(name, payload = {}) {
  try {
    // eslint-disable-next-line no-console
    console.log('[analytics]', name, payload);

    // future: send to backend
    // fetch('/api/analytics', {
    //   method: 'POST',
    //   headers: { 'Content-Type': 'application/json' },
    //   body: JSON.stringify({ name, payload, timestamp: Date.now() }),
    // });
  } catch (e) {
    // fail silently
  }
}
