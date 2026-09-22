import Image from "next/image";

export default function Logo({ height = 96 }: { height?: number }) {
  return (
    <Image
      src="/fyve-logo.png"
      alt="FYVE"
      width={height * 3.09}
      height={height}
      priority
      style={{ height, width: "auto" }}
    />
  );
}
