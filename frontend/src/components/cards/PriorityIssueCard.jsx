import { motion } from "framer-motion";

function PriorityIssueCard({
  issue,
}) {

  return (

    <motion.div
      initial={{
        opacity: 0,
        x: -20,
      }}
      whileInView={{
        opacity: 1,
        x: 0,
      }}
      transition={{
        duration: 0.35,
      }}
      viewport={{
        once: true,
      }}
      className="
        bg-red-500/10
        border
        border-red-500/20
        rounded-2xl
        p-5
        backdrop-blur-xl
      "
    >

      {/* HEADER */}
      <div className="
        flex
        items-start
        justify-between
        gap-4
        mb-4
      ">

        <div>

          <div className="
            text-red-300
            text-xs
            mb-2
          ">
            CRITICAL ISSUE
          </div>

          <h3 className="
            text-xl
            font-semibold
            text-white
          ">
            {issue.check}
          </h3>

        </div>

        <div className="
          px-3
          py-1
          rounded-full
          bg-red-500/20
          text-red-300
          text-xs
        ">
          FAIL
        </div>

      </div>

      {/* DETAIL */}
      <p className="
        text-gray-300
        leading-relaxed
        mb-5
      ">
        {issue.detail}
      </p>

      {/* FIX */}
      {issue.ai_fix && (

        <div className="
          bg-black/20
          rounded-xl
          p-4
          border
          border-white/5
        ">

          <div className="
            text-sm
            text-red-300
            mb-2
          ">
            Recommended Action
          </div>

          <div className="
            text-sm
            text-gray-300
            leading-relaxed
            whitespace-pre-wrap
          ">
            {issue.ai_fix}
          </div>

        </div>

      )}

    </motion.div>
  );
}

export default PriorityIssueCard;