export function Logo({ size = "md" }: { size?: "md" | "lg" }) {
  const large = size === "lg";
  return (
    <div className="flex items-center gap-2.5">
      <svg
        className={large ? "h-10 w-12" : "h-8 w-10"}
        viewBox="0 0 40 34"
        fill="none"
        aria-hidden="true"
      >
        <path d="M2 12c6-1 12 0 18 5v15C14 28 8 27 2 28V12Z" fill="#121212" />
        <path d="M38 12c-6-1-12 0-18 5v15c6-4 12-5 18-4V12Z" fill="#121212" />
        <path d="M9 7c4 0 8 1.5 11 5-3-1-7-1.5-11-1V7Zm22 0c-4 0-8 1.5-11 5 3-1 7-1.5 11-1V7Z" fill="#fdb022" />
        <path d="M20 0l1.6 3.4L25 5l-3.400 1.600L20 10l-1.600-3.400L15 5l3.400-1.600L20 0Z" fill="#fdb022" />
      </svg>
      <span className={`${large ? "text-4xl" : "text-2xl sm:text-3xl"} font-extrabold tracking-tight`}>
        Sakhi <span className="text-accent">AI</span>
      </span>
    </div>
  );
}
