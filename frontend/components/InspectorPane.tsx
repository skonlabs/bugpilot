export const InspectorPane = () => {
  return (
    <div className="flex h-full w-[400px] shrink-0 flex-col bg-background">
      {/* Header */}
      <div className="flex items-center border-b border-border px-4 py-3">
        <span className="text-[11px] tracking-wider text-echo">
          INSPECTOR
        </span>
      </div>

      {/* Empty State */}
      <div className="flex flex-1 flex-col items-center justify-center px-6">
        <p className="text-[11px] tracking-wider text-echo text-center leading-relaxed">
          NO TARGET ACQUIRED.
          <br />
          SELECT AN ANOMALY TO INSPECT.
        </p>
      </div>
    </div>
  );
};
