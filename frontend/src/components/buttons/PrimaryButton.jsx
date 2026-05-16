function PrimaryButton({ children, onClick }) {
  return (
    <button
      onClick={onClick}
      className="
        bg-blue-600
        hover:bg-blue-500
        transition
        px-6
        py-3
        rounded-xl
        font-medium
        shadow-lg
        shadow-blue-500/20
      "
    >
      {children}
    </button>
  );
}

export default PrimaryButton;