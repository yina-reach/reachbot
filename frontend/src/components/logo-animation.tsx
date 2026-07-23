/**
 * The animated ReachBot logo, used as the loading indicator. It's a square GIF
 * served from /public — no JS runtime, the browser paints it natively (much
 * lighter than a Lottie player). Kept as a component so callers stay unchanged.
 */
export function LogoAnimation({ className }: { className?: string }) {
  return (
    /* eslint-disable-next-line @next/next/no-img-element */
    <img src="/reachbot-loader.gif" alt="" aria-hidden className={className} />
  );
}
