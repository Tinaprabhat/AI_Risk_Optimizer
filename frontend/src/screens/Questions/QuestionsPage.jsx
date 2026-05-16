import { useState } from "react";

import MainLayout from "../../layouts/MainLayout";

import useAuditStore from "../../store/auditStore";

import { useNavigate } from "react-router-dom";

function QuestionsPage() {

  const setQuestions = useAuditStore(
    (state) => state.setQuestions
  );


  const storeUrl = useAuditStore(
    (state) => state.storeUrl
  );

  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    category: "",
    customer: "",
    differentiator: "",
    tone: "",
  });

  const handleChange = (field, value) => {

    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

    const handleContinue = () => {

    setQuestions(formData);

    console.log("STORE URL:", storeUrl);

    console.log("QUESTIONS:", formData);
    navigate("/scanning");};
  return (
    <MainLayout>

      <div className="max-w-4xl mx-auto px-6 py-20">

        <div className="mb-10">

          <div className="text-blue-400 text-sm mb-4">
            Step 2 of 5
          </div>

          <h1 className="text-5xl font-bold mb-4">
            Tell us about your store
          </h1>

          <p className="text-gray-400 text-lg">
            This helps our AI understand your brand positioning.
          </p>

        </div>

        {/* FORM */}
        <div className="space-y-6">

          {/* CATEGORY */}
          <div>

            <label className="block mb-2 text-sm text-gray-300">
              Category
            </label>

            <input
              type="text"
              placeholder="e.g. Fitness Apparel"
              value={formData.category}
              onChange={(e) =>
                handleChange("category", e.target.value)
              }
              className="
                w-full
                bg-white/5
                border
                border-white/10
                rounded-xl
                px-5
                py-4
                outline-none
              "
            />

          </div>

          {/* CUSTOMER */}
          <div>

            <label className="block mb-2 text-sm text-gray-300">
              Target Customer
            </label>

            <input
              type="text"
              placeholder="e.g. Gym enthusiasts"
              value={formData.customer}
              onChange={(e) =>
                handleChange("customer", e.target.value)
              }
              className="
                w-full
                bg-white/5
                border
                border-white/10
                rounded-xl
                px-5
                py-4
                outline-none
              "
            />

          </div>

          {/* DIFFERENTIATOR */}
          <div>

            <label className="block mb-2 text-sm text-gray-300">
              Differentiator
            </label>

            <input
              type="text"
              placeholder="e.g. Sustainable materials"
              value={formData.differentiator}
              onChange={(e) =>
                handleChange("differentiator", e.target.value)
              }
              className="
                w-full
                bg-white/5
                border
                border-white/10
                rounded-xl
                px-5
                py-4
                outline-none
              "
            />

          </div>

          {/* TONE */}
          <div>

            <label className="block mb-2 text-sm text-gray-300">
              Brand Tone
            </label>

            <input
              type="text"
              placeholder="e.g. Modern energetic"
              value={formData.tone}
              onChange={(e) =>
                handleChange("tone", e.target.value)
              }
              className="
                w-full
                bg-white/5
                border
                border-white/10
                rounded-xl
                px-5
                py-4
                outline-none
              "
            />

          </div>

        </div>

        {/* CTA */}
        <div className="mt-10 flex justify-end">

          <button
            onClick={handleContinue}
            className="
              bg-blue-600
              hover:bg-blue-500
              transition
              px-8
              py-4
              rounded-xl
              font-medium
            "
          >
            Continue →
          </button>

        </div>

      </div>

    </MainLayout>
  );
}

export default QuestionsPage;