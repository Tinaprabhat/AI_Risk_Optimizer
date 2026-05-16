function Navbar() {
  return (
    <nav className="flex items-center justify-between mb-20">

      <div className="flex items-center gap-2">
        <div className="w-3 h-3 rounded-full bg-blue-500" />

        <span className="font-semibold text-lg">
          AI Visibility
        </span>
      </div>

      <div className="flex items-center gap-8 text-sm text-gray-300">

        <button className="hover:text-white transition">
          How it Works
        </button>

        <button className="hover:text-white transition">
          View Demo
        </button>

        <button className="bg-blue-600 hover:bg-blue-500 transition px-4 py-2 rounded-xl">
          Get Started →
        </button>
      </div>
    </nav>
  );
}

export default Navbar;