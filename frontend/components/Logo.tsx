import Image from "next/image";

export default function Logo({ height = 28 }: { height?: number }) {
  return (
    <Image
      src="/fyve-logo.webp"
      alt="FYVE"
      width={height * 3.4}
      height={height}
      priority
      style={{ height, width: "auto" }}
    />
  );
}
