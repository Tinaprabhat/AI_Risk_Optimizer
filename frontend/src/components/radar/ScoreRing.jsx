function ScoreRing({ score }) {

  const radius = 90;

  const circumference =
    2 * Math.PI * radius;

  const progress =
    circumference -
    (score / 100) * circumference;

  return (
    <div className="
      relative
      w-[240px]
      h-[240px]
      flex
      items-center
      justify-center
    ">

      <svg
        width="240"
        height="240"
        className="-rotate-90"
      >

        {/* BACKGROUND */}
        <circle
          cx="120"
          cy="120"
          r={radius}
          stroke="rgba(255,255,255,0.08)"
          strokeWidth="14"
          fill="transparent"
        />

        {/* PROGRESS */}
        <circle
          cx="120"
          cy="120"
          r={radius}
          stroke="#3b82f6"
          strokeWidth="14"
          fill="transparent"
          strokeDasharray={circumference}
          strokeDashoffset={progress}
          strokeLinecap="round"
          style={{
            transition:
              "stroke-dashoffset 1s ease",
          }}
        />

      </svg>

      {/* CENTER TEXT */}
      <div className="
        absolute
        flex
        flex-col
        items-center
      ">

        <div className="text-6xl font-bold">
          {score}%
        </div>

        <div className="text-gray-400 text-sm mt-2">
          AI Visibility
        </div>

      </div>

    </div>
  );
}

export default ScoreRing;