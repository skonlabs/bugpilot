export const QueuePane = () => {
  return (
    <div className="flex h-full flex-1 flex-col border-r border-border bg-background">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <span className="text-[11px] tracking-wider text-echo">
          ANOMALY QUEUE
        </span>
        <span className="text-[11px] text-echo">0</span>
      </div>

      {/* Empty State */}
      <div className="flex flex-1 flex-col items-center justify-center px-6">
        <p className="text-[11px] tracking-wider text-echo">
          <span className="cursor-blink text-intercept">▌</span>
          {" "}[SYSTEM NOMINAL. ZERO ANOMALIES DETECTED.]
        </p>
      </div>
    </div>
  );
};
