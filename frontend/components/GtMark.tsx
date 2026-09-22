"use client";

import { useEffect, useRef, useState } from "react";

/** Persistent Georgia Tech marker, pinned bottom-centre on every screen.
 *
 * Decorative and non-interactive: it sits behind everything and ignores
 * pointer events so it can never intercept a click on the content above it.
 *
 * Artwork: drop the official interlocking-GT file in at
 * `public/gt-logo.png` and it's picked up automatically. Until that file
 * exists this falls back to `public/gt-mark.svg`, an original geometric GT
 * monogram, so the layout never shows a broken image.
 */
export default function GtMark() {
  const [useFallback, setUseFallback] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);

  // The browser starts loading the image while parsing the server-rendered
  // HTML, so a 404 can fire its error event before React has attached
  // onError - leaving a broken image and no fallback. Re-check the outcome
  // once on mount to catch a failure that already happened.
  useEffect(() => {
    const img = imgRef.current;
    if (img && img.complete && img.naturalWidth === 0) {
      setUseFallback(true);
    }
  }, []);

  return (
    <div className="gt-mark" aria-hidden="true">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        ref={imgRef}
        src={useFallback ? "/gt-mark.svg" : "/gt-logo.png"}
        alt=""
        height={58}
        onError={() => setUseFallback(true)}
      />
    </div>
  );
}
