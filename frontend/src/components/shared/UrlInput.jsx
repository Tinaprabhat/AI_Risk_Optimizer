import { useState } from "react";

import { useNavigate } from "react-router-dom";

import PrimaryButton from "../buttons/PrimaryButton";

import useAuditStore from "../../store/auditStore";

function UrlInput() {

  const [url, setUrl] = useState("");
  const setStoreUrl = useAuditStore((state) => state.setStoreUrl);
  const navigate = useNavigate();

  const handleScan = () => {

    if (!url) return;

    setStoreUrl(url);
    navigate("/questions");
  };

  return (
    <div className="
      max-w-3xl
      mx-auto
      bg-white/5
      border
      border-white/10
      rounded-2xl
      p-3
      flex
      items-center
      gap-3
      backdrop-blur-xl
      shadow-2xl
      shadow-blue-900/10
    ">

      <input
        type="text"
        placeholder="Enter your Shopify store URL..."
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        className="
          flex-1
          bg-transparent
          outline-none
          px-4
          py-3
          text-white
          placeholder:text-gray-500
        "
      />

      <PrimaryButton onClick={handleScan}>
        Scan Store
      </PrimaryButton>

    </div>
  );
}

export default UrlInput;