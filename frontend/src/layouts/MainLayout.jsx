function MainLayout({ children }) {
  return (
    <div className="relative min-h-screen overflow-hidden bg-[#050816] text-white">

      {/* BACKGROUND GLOW */}
      <div className="absolute top-[-200px] right-[-100px] w-[500px] h-[500px] bg-blue-600/20 blur-[140px] rounded-full" />

      <div className="absolute bottom-[-250px] left-[-100px] w-[500px] h-[500px] bg-cyan-500/10 blur-[140px] rounded-full" />

      {/* GRID OVERLAY */}
      <div
        className="absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage:
            "linear-gradient(to right, white 1px, transparent 1px), linear-gradient(to bottom, white 1px, transparent 1px)",
          backgroundSize: "80px 80px",
        }}
      />

      {/* CONTENT */}
      <div className="relative z-10">
        {children}
      </div>
    </div>
  );
}

export default MainLayout;