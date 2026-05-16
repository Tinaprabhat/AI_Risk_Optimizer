const platforms = [
  "ChatGPT",
  "Claude",
  "Gemini",
  "Perplexity",
  "Google AI",
];

function PlatformPills() {
  return (
    <div className="flex flex-wrap justify-center gap-4 mt-10">

      {platforms.map((item) => (
        <div
          key={item}
          className="px-4 py-2 rounded-full bg-white/5 border border-white/10 text-sm text-gray-300"
        >
          {item}
        </div>
      ))}
    </div>
  );
}

export default PlatformPills;