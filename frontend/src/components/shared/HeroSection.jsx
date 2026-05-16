import { motion } from "framer-motion";

function HeroSection() {
  return (
    <motion.section
      initial={{ opacity: 0, y: 40 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.8 }}
      className="text-center"
    >

      <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-blue-500/30 bg-blue-500/10 text-sm text-blue-300 mb-8">
        <span>⚡</span>
        <span>AI Search Visibility Scanner</span>
      </div>

      <h1 className="text-6xl font-bold leading-tight max-w-5xl mx-auto mb-6">

        Is Your Store Visible to{" "}

        <span className="text-blue-400">
          AI Search Engines?
        </span>

      </h1>

      <p className="text-gray-400 text-lg max-w-2xl mx-auto mb-12">
        Analyze how ChatGPT, Gemini, Claude, and AI crawlers
        understand your ecommerce store.
      </p>

    </motion.section>
  );
}

export default HeroSection;