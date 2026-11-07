// Soft yellow/orange corner shapes from the Sakhi AI design.
export function CornerShapes() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
      <div className="absolute -left-32 -top-36 size-72 rounded-full bg-accent-soft/70 sm:-left-40 sm:-top-44 sm:size-[22rem]" />
      <div className="absolute -left-16 -top-20 size-40 rounded-full bg-linear-to-br from-accent to-[#ffc34d] sm:-left-24 sm:-top-28 sm:size-60" />
      <div className="absolute -bottom-40 -right-40 size-80 rounded-full bg-accent-soft/70 sm:-bottom-44 sm:-right-48 sm:size-[28rem]" />
      <div className="absolute -bottom-24 -right-20 size-52 rounded-full bg-linear-to-br from-[#ffc34d] to-accent sm:-bottom-32 sm:-right-24 sm:size-72" />
    </div>
  );
}
