import { useState } from "react";

import {
  motion,
  AnimatePresence,
} from "framer-motion";

import CheckCard from "./CheckCard";

function LayerSection({
  title,
  description,
  checks,
}) {

  const [open, setOpen] =
    useState(true);

  if (!checks?.length) return null;

  const passed =
    checks.filter(
      (item) => item.status === "PASS"
    ).length;

  const failed =
    checks.length - passed;

  return (

    <div className="mb-10">

      {/* HEADER */}
      <button
        onClick={() => setOpen(!open)}
        className="
          w-full
          bg-white/5
          border
          border-white/10
          rounded-2xl
          p-6
          backdrop-blur-xl
          flex
          items-center
          justify-between
          text-left
          hover:border-blue-500/30
          transition-all
          duration-300
        "
      >

        <div>

          {/* TOP */}
          <div className="
            flex
            items-center
            gap-3
            mb-3
            flex-wrap
          ">

            <h2 className="
              text-2xl
              font-bold
            ">
              {title}
            </h2>

            {/* PASSED */}
            <div className="
              px-3
              py-1
              rounded-full
              bg-green-500/10
              text-green-300
              text-xs
            ">
              {passed} Passed
            </div>

            {/* FAILED */}
            <div className="
              px-3
              py-1
              rounded-full
              bg-red-500/10
              text-red-300
              text-xs
            ">
              {failed} Failed
            </div>

          </div>

          {/* DESCRIPTION */}
          <p className="
            text-gray-400
            leading-relaxed
            max-w-3xl
          ">
            {description}
          </p>

        </div>

        {/* TOGGLE */}
        <motion.div
          animate={{
            rotate: open ? 180 : 0,
          }}
          transition={{
            duration: 0.3,
          }}
          className="
            text-3xl
            text-blue-400
            ml-6
          "
        >
          ⌄
        </motion.div>

      </button>

      {/* BODY */}
      <AnimatePresence>

        {open && (

          <motion.div
            initial={{
              opacity: 0,
              height: 0,
            }}
            animate={{
              opacity: 1,
              height: "auto",
            }}
            exit={{
              opacity: 0,
              height: 0,
            }}
            transition={{
              duration: 0.35,
            }}
            className="
              overflow-hidden
            "
          >

            <div className="
              grid
              grid-cols-1
              md:grid-cols-2
              gap-6
              mt-6
            ">

              {checks.map((check) => (

                <CheckCard
                  key={check.check}
                  check={check}
                />

              ))}

            </div>

          </motion.div>

        )}

      </AnimatePresence>

    </div>
  );
}

export default LayerSection;