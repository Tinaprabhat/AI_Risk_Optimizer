function ScoreCard({
  title,
  value,
  subtitle,
}) {
  return (
    <div className="
      bg-white/5
      border
      border-white/10
      rounded-2xl
      p-8
      backdrop-blur-xl
    ">

      <div className="text-sm text-gray-400 mb-3">
        {title}
      </div>

      <div className="text-5xl font-bold mb-3">
        {value}
      </div>

      <div className="text-gray-500 text-sm">
        {subtitle}
      </div>

    </div>
  );
}

export default ScoreCard;