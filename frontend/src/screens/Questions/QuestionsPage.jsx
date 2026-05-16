
import { useState } from "react";

import { motion, AnimatePresence } from "framer-motion";

import { useNavigate } from "react-router-dom";

import MainLayout from "../../layouts/MainLayout";

import useAuditStore from "../../store/auditStore";

const questions = [

  {
    key: "category",

    text:
      "What type of products does your store sell?",

    opts: [
      "Fashion & Apparel",
      "Electronics & Tech",
      "Home & Living",
      "Health & Beauty",
      "Food & Supplements",
      "Other",
    ],
  },

  {
    key: "store_age",

    text:
      "How long has your store been running?",

    opts: [
      "Just launched (under 3 months)",
      "Growing (3–12 months)",
      "Established (1–3 years)",
      "Mature (3+ years)",
    ],
  },

  {
    key: "traffic",

    text:
      "How many visitors does your store get monthly?",

    opts: [
      "Under 500 visitors",
      "500 – 5,000 visitors",
      "5,000 – 50,000 visitors",
      "Over 50,000 visitors",
      "I don't know",
    ],
  },

  {
    key: "challenge",

    text:
      "What is your biggest challenge right now?",

    opts: [
      "Getting more traffic",
      "Converting visitors to buyers",
      "Standing out from competitors",
      "Building customer trust",
      "All of the above",
    ],
  },

  {
    key: "ai_optimization",

    text:
      "Have you ever optimized your store for AI shopping recommendations before?",

    opts: [
      "Yes, extensively",
      "Yes, a little",
      "No, but I want to",
      "I didn't know this was possible",
    ],
  },
];

function QuestionsPage() {

  const navigate = useNavigate();

  const setQuestions = useAuditStore(
    (state) => state.setQuestions
  );

  const [step, setStep] =
    useState(0);

  const [answers, setAnswers] =
    useState({});

  const [otherInput, setOtherInput] =
    useState("");

  const currentQuestion =
    questions[step];

  const progress =
    ((step + 1) /
      questions.length) *
    100;

  const handleSelect = (option) => {

    const updatedAnswers = {
      ...answers,
      [currentQuestion.key]: option,
    };

    setAnswers(updatedAnswers);

    // OTHER OPTION
    if (option === "Other") {
      return;
    }

    // NEXT QUESTION
    if (
      step < questions.length - 1
    ) {

      setTimeout(() => {
        setStep(step + 1);
      }, 350);

    }

    // FINISH
    else {

      setQuestions(updatedAnswers);

      setTimeout(() => {
        navigate("/scanning");
      }, 500);
    }
  };

  const submitOther = () => {

    if (!otherInput) return;

    const updatedAnswers = {
      ...answers,
      [currentQuestion.key]: otherInput,
    };

    setAnswers(updatedAnswers);

    if (
      step < questions.length - 1
    ) {

      setStep(step + 1);

      setOtherInput("");

    }

    else {

      setQuestions(updatedAnswers);

      navigate("/scanning");
    }
  };

  return (

    <MainLayout>

      <div className="
        min-h-screen
        flex
        items-center
        justify-center
        px-6
        py-20
      ">

        <div className="
          w-full
          max-w-4xl
        ">

          {/* TOP */}
          <div className="mb-10">

            <div className="
              flex
              items-center
              justify-between
              mb-4
            ">

              <div className="
                text-blue-400
                text-sm
              ">
                Step {step + 1} of {questions.length}
              </div>

              <div className="
                text-sm
                text-gray-400
              ">
                {Math.round(progress)}%
              </div>

            </div>

            {/* PROGRESS BAR */}
            <div className="
              w-full
              h-3
              rounded-full
              bg-white/10
              overflow-hidden
            ">

              <div
                className="
                  h-full
                  bg-blue-500
                  transition-all
                  duration-500
                "
                style={{
                  width: `${progress}%`,
                }}
              />

            </div>

          </div>

          {/* QUESTION CARD */}
          <AnimatePresence mode="wait">

            <motion.div
              key={step}
              initial={{
                opacity: 0,
                x: 80,
              }}
              animate={{
                opacity: 1,
                x: 0,
              }}
              exit={{
                opacity: 0,
                x: -80,
              }}
              transition={{
                duration: 0.35,
              }}
              className="
                bg-white/5
                border
                border-white/10
                rounded-3xl
                p-10
                backdrop-blur-xl
              "
            >

              {/* QUESTION */}
              <h1 className="
                text-4xl
                md:text-5xl
                font-bold
                leading-tight
                mb-10
              ">
                {currentQuestion.text}
              </h1>

              {/* OPTIONS */}
              <div className="space-y-4">

                {currentQuestion.opts.map(
                  (option) => (

                    <button
                      key={option}
                      onClick={() =>
                        handleSelect(option)
                      }
                      className="
                        w-full
                        text-left
                        px-6
                        py-5
                        rounded-2xl
                        bg-white/5
                        border
                        border-white/10
                        hover:border-blue-500/40
                        hover:bg-blue-500/10
                        transition-all
                        duration-300
                        text-lg
                      "
                    >
                      {option}
                    </button>

                ))}

              </div>

              {/* OTHER INPUT */}
              {answers[currentQuestion.key] ===
                "Other" && (

                <div className="mt-8">

                  <textarea
                    value={otherInput}
                    onChange={(e) =>
                      setOtherInput(
                        e.target.value
                      )
                    }
                    placeholder="Describe your store..."
                    className="
                      w-full
                      min-h-[140px]
                      bg-black/20
                      border
                      border-white/10
                      rounded-2xl
                      px-5
                      py-4
                      outline-none
                      resize-none
                    "
                  />

                  <button
                    onClick={submitOther}
                    className="
                      mt-5
                      px-8
                      py-4
                      rounded-2xl
                      bg-blue-600
                      hover:bg-blue-500
                      transition-all
                    "
                  >
                    Continue →
                  </button>

                </div>

              )}

            </motion.div>

          </AnimatePresence>

        </div>

      </div>

    </MainLayout>
  );
}

export default QuestionsPage;
