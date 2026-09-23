/** Start-over control, fixed in the top-left on every screen.
 *
 * A plain link to "/" rather than a state reset: a full page load clears
 * every bit of in-progress state (chosen term, course, answers, results)
 * with no chance of something stale surviving, and it works even if React
 * hasn't hydrated.
 */
export default function HomeButton() {
  return (
    <a className="home-button" href="/" aria-label="Start over from the beginning" title="Start over">
      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" aria-hidden="true">
        <path
          d="M3 11.5 12 4l9 7.5"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M5.5 10.5V19a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1v-8.5"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </a>
  );
}
