import { useState } from "react";

import { motion } from "framer-motion";

function CheckCard({ check }) {

  const [expanded, setExpanded] =
    useState(false);

  const passed =
    check.status === "PASS";

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
        bg-white/5
        border
        border-white/10
        rounded-2xl
        p-6
        backdrop-blur-xl
        hover:border-blue-500/30
        transition-all
        duration-300
      "
    >

      {/* TOP */}
      <div className="
        flex
        items-start
        justify-between
        gap-4
      ">

        <div className="flex-1">

          <div className="
            text-sm
            text-gray-400
            mb-2
          ">
            {check.check}
          </div>

          <h3 className="
            text-xl
            font-semibold
            mb-3
            leading-relaxed
          ">
            {check.detail}
          </h3>

          <div className="
            flex
            items-center
            gap-3
            flex-wrap
          ">

            {/* STATUS */}
            <div
              className={`
                px-4
                py-2
                rounded-full
                text-sm
                font-medium
                ${passed
                  ? "bg-green-500/20 text-green-300"
                  : "bg-red-500/20 text-red-300"
                }
              `}
            >
              {check.status}
            </div>

            {/* TIER */}
            <div className="
              px-3
              py-1
              rounded-full
              bg-blue-500/10
              text-blue-300
              text-xs
            ">
              {check.tier}
            </div>

          </div>

        </div>

        {/* TOGGLE */}
        <button
          onClick={() =>
            setExpanded(!expanded)
          }
          className="
            text-sm
            text-blue-400
            hover:text-blue-300
            transition
          "
        >
          {expanded
            ? "Hide"
            : "Details"}
        </button>

      </div>

      {/* EXPANDED */}
      {expanded && (

        <motion.div
          initial={{
            opacity: 0,
            height: 0,
          }}
          animate={{
            opacity: 1,
            height: "auto",
          }}
          transition={{
            duration: 0.35,
          }}
          className="
            mt-6
            pt-6
            border-t
            border-white/10
          "
        >

          {/* EVIDENCE */}
          {check.evidence && (

            <div className="mb-6">

              <div className="
                text-sm
                text-gray-400
                mb-2
              ">
                Evidence
              </div>

              <div className="
                bg-black/30
                rounded-xl
                p-4
                text-sm
                text-gray-300
                overflow-auto
                max-h-60
                leading-relaxed
                border
                border-white/5
              ">
                {String(check.evidence)}
              </div>

            </div>
          )}

          {/* FIX */}
          {!passed && (

            <div>

              <div className="
                text-sm
                text-gray-400
                mb-2
              ">
                Recommended Fix
              </div>

              <div className="
                bg-blue-500/10
                border
                border-blue-500/20
                rounded-xl
                p-4
                text-sm
                text-blue-100
                whitespace-pre-wrap
                leading-relaxed
              ">

                {check.ai_fix || `
Improve this audit category
by optimizing semantic
structure, metadata,
crawlability, and AI
readability.
                `}

              </div>

            </div>
          )}

        </motion.div>
      )}

    </motion.div>
  );
}

export default CheckCard;