// A number drawn with base-ten blocks: one tall rod per ten, one small cube per one.
export function BaseTenBlocks({ value }: { value: number }) {
  const tens = Math.floor(value / 10);
  const ones = value % 10;
  return (
    <div className="flex items-end gap-1.5" role="img" aria-label={`${tens} tens and ${ones} ones`}>
      {Array.from({ length: tens }, (_, i) => (
        <div
          key={`ten-${i}`}
          className="h-20 w-4 rounded-[3px] border border-[#d98c00] sm:h-24 sm:w-5"
          style={{
            background:
              "repeating-linear-gradient(to bottom, #fdb022 0 calc(10% - 1.5px), #d98c00 calc(10% - 1.5px) 10%)",
          }}
        />
      ))}
      <div className="ml-1 flex items-end gap-1">
        {Array.from({ length: ones }, (_, i) => (
          <div key={`one-${i}`} className="size-4 rounded-[3px] border border-[#d98c00] bg-accent sm:size-5" />
        ))}
      </div>
    </div>
  );
}
