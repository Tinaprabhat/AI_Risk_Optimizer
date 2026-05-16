import { motion } from "framer-motion";

function SummaryCard({
  title,
  description,
  severity = "info",
}) {

  const severityStyles = {

    success:
      "bg-green-500/10 border-green-500/20 text-green-200",

    warning:
      "bg-yellow-500/10 border-yellow-500/20 text-yellow-200",

    danger:
      "bg-red-500/10 border-red-500/20 text-red-200",

    info:
      "bg-blue-500/10 border-blue-500/20 text-blue-200",

  };

  return (

    <motion.div
      initial={{
        opacity: 0,
        y: 20,
      }}
      whileInView={{
        opacity: 1,
        y: 0,
      }}
      transition={{
        duration: 0.4,
      }}
      viewport={{
        once: true,
      }}
      className={`
        border
        rounded-2xl
        p-6
        backdrop-blur-xl
        ${severityStyles[severity]}
      `}
    >

      <h3 className="
        text-xl
        font-semibold
        mb-3
      ">
        {title}
      </h3>

      <p className="
        leading-relaxed
        text-sm
      ">
        {description}
      </p>

    </motion.div>
  );
}

export default SummaryCard;