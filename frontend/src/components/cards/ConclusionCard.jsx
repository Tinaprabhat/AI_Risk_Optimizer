import { motion } from "framer-motion";

function ConclusionCard({
  score,
  checks,
}) {

  // FAILED CHECK NAMES
  const failedNames = checks
    .filter(
      (item) => item.status === "FAIL"
    )
    .slice(0, 5)
    .map((item) => item.check);

  // AI SUMMARY
  const summary =
    score >= 80
      ? "Your store demonstrates strong AI visibility and recommendation readiness. Most critical discoverability, semantic, and trust signals are properly optimized, allowing AI systems to confidently understand and recommend your ecommerce experience."

      : score >= 60
      ? "Your store has moderate AI visibility but still contains important optimization gaps. While AI systems can partially understand your store, missing semantic consistency, metadata depth, or trust signals may reduce recommendation confidence."

      : "Your store currently lacks several critical AI visibility signals. AI systems may struggle to confidently crawl, interpret, and recommend your products due to weak semantic structure, incomplete metadata, or insufficient trust and recommendation indicators.";

  return (

    <motion.div
      initial={{
        opacity: 0,
        y: 30,
      }}
      whileInView={{
        opacity: 1,
        y: 0,
      }}
      transition={{
        duration: 0.5,
      }}
      viewport={{
        once: true,
      }}
      className="
        bg-gradient-to-br
        from-blue-500/10
        to-cyan-500/10
        border
        border-blue-500/20
        rounded-3xl
        p-8
        backdrop-blur-xl
        mb-20
      "
    >

      {/* HEADER */}
      <div className="mb-6">

        <div className="
          text-cyan-300
          text-sm
          mb-3
        ">
          AI GENERATED CONCLUSION
        </div>

        <h2 className="
          text-4xl
          font-bold
          mb-4
        ">
          Why Your Store May Not Be
          Recommended by AI Systems
        </h2>

      </div>

      {/* SUMMARY */}
      <p className="
        text-gray-300
        text-lg
        leading-relaxed
        mb-8
      ">
        {summary}
      </p>

      {/* FAILED RULES */}
      {failedNames.length > 0 && (

        <div>

          <div className="
            text-sm
            text-gray-400
            mb-4
          ">
            Key Failed Audit Rules
          </div>

          <div className="
            flex
            flex-wrap
            gap-3
          ">

            {failedNames.map((item) => (

              <div
                key={item}
                className="
                  px-4
                  py-2
                  rounded-full
                  bg-red-500/10
                  border
                  border-red-500/20
                  text-red-300
                  text-sm
                "
              >
                {item}
              </div>

            ))}

          </div>

        </div>

      )}

      {/* FOOTER */}
      <div className="
        mt-8
        pt-6
        border-t
        border-white/10
        text-sm
        text-gray-400
        leading-relaxed
      ">

        AI recommendation systems rely heavily on
        structured metadata, semantic clarity,
        crawlability, trust signals, and contextual
        understanding to confidently surface ecommerce stores.

      </div>

    </motion.div>

  );
}

export default ConclusionCard;