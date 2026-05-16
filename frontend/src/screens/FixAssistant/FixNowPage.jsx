import { useState } from "react";

import MainLayout from "../../layouts/MainLayout";

import useAuditStore from "../../store/auditStore";
import { sendChatMessage } from "../../services/chatService";

function FixNowPage() {

  const auditResult = useAuditStore(
    (state) => state.auditResult
  );

  const failedChecks = Object.values(
    auditResult?.checks || {}
  ).filter(
    (item) => item.status === "FAIL"
  );

  const [completed, setCompleted] =
    useState([]);

  const [messages, setMessages] =
    useState([
      {
        role: "assistant",
        content:
          "Hi — I can help you fix your AI visibility issues. Select a failed rule or ask me how to improve your store.",
      },
    ]);

  const [input, setInput] =
    useState("");

  // TOGGLE CHECKBOX
  const toggleCheck = (rule) => {

    if (completed.includes(rule)) {

      setCompleted(
        completed.filter(
          (item) => item !== rule
        )
      );

    }

    else {

      setCompleted([
        ...completed,
        rule,
      ]);

    }
  };

  // SEND MESSAGE
  const sendMessage = async () => {

  if (!input) return;

  const userMessage = {
    role: "user",
    content: input,
  };

  // SHOW USER MESSAGE
  setMessages((prev) => [
    ...prev,
    userMessage,
  ]);

  const currentInput = input;

  setInput("");

  try {

    // CALL BACKEND AI
    const response =
      await sendChatMessage(

        currentInput,

        failedChecks.map(
          (item) => item.check
        )

      );

    // SHOW AI RESPONSE
    setMessages((prev) => [

      ...prev,

      {
        role: "assistant",
        content:
          response.response,
      },

    ]);

  }

  catch (error) {

    console.error(error);

    setMessages((prev) => [

      ...prev,

      {
        role: "assistant",
        content:
          "AI assistant failed. Please try again.",
      },

    ]);

  }
};
  return (

    <MainLayout>

      <div className="
        max-w-7xl
        mx-auto
        px-6
        py-20
      ">

        {/* HEADER */}
        <div className="mb-14">

          <div className="
            text-blue-400
            text-sm
            mb-4
          ">
            AI Fix Assistant
          </div>

          <h1 className="
            text-5xl
            font-bold
            mb-6
          ">
            Resolve Your AI Visibility Issues
          </h1>

          <p className="
            text-gray-400
            text-lg
            max-w-3xl
          ">
            Track failed audit rules and use the AI assistant to learn how to fix discoverability, semantic, and recommendation issues.
          </p>

        </div>

        {/* MAIN GRID */}
        <div className="
          grid
          grid-cols-1
          lg:grid-cols-[420px_1fr]
          gap-8
        ">

          {/* LEFT SIDE */}
          <div className="
            bg-white/5
            border
            border-white/10
            rounded-3xl
            p-6
            backdrop-blur-xl
            h-fit
          ">

            <div className="
              flex
              items-center
              justify-between
              mb-6
            ">

              <h2 className="
                text-2xl
                font-bold
              ">
                Failed Rules
              </h2>

              <div className="
                text-sm
                text-gray-400
              ">
                {completed.length}/
                {failedChecks.length}
              </div>

            </div>

            <div className="space-y-4">

              {failedChecks.map((item) => (

                <div
                  key={item.check}
                  className="
                    bg-black/20
                    border
                    border-white/10
                    rounded-2xl
                    p-4
                  "
                >

                  <div className="
                    flex
                    items-start
                    gap-4
                  ">

                    <input
                      type="checkbox"
                      checked={completed.includes(
                        item.check
                      )}
                      onChange={() =>
                        toggleCheck(
                          item.check
                        )
                      }
                      className="
                        mt-1
                        w-5
                        h-5
                      "
                    />

                    <div>

                      <div className="
                        font-semibold
                        mb-2
                      ">
                        {item.check}
                      </div>

                      <div className="
                        text-sm
                        text-gray-400
                        leading-relaxed
                      ">
                        {item.detail}
                      </div>

                    </div>

                  </div>

                </div>

              ))}

            </div>

          </div>

          {/* RIGHT SIDE */}
          <div className="
            bg-white/5
            border
            border-white/10
            rounded-3xl
            backdrop-blur-xl
            flex
            flex-col
            overflow-hidden
            min-h-[700px]
          ">

            {/* CHAT HEADER */}
            <div className="
              border-b
              border-white/10
              px-6
              py-5
            ">

              <div className="
                text-xl
                font-bold
                mb-1
              ">
                AI Fix Assistant
              </div>

              <div className="
                text-sm
                text-gray-400
              ">
                Specialized AI assistant for fixing failed audit rules.
              </div>

            </div>

            {/* MESSAGES */}
            <div className="
              flex-1
              overflow-y-auto
              p-6
              space-y-5
            ">

              {messages.map(
                (message, index) => (

                  <div
                    key={index}
                    className={`
                      max-w-[80%]
                      rounded-2xl
                      px-5
                      py-4
                      leading-relaxed
                      ${
                        message.role ===
                        "assistant"
                          ? "bg-blue-500/10 border border-blue-500/20"
                          : "bg-white/10 ml-auto"
                      }
                    `}
                  >
                    {message.content}
                  </div>

              ))}

            </div>

            {/* INPUT */}
            <div className="
              border-t
              border-white/10
              p-5
              flex
              gap-4
            ">

              <input
                type="text"
                value={input}
                onChange={(e) =>
                  setInput(e.target.value)
                }
                placeholder="Ask how to fix failed rules..."
                className="
                  flex-1
                  bg-black/20
                  border
                  border-white/10
                  rounded-2xl
                  px-5
                  py-4
                  outline-none
                "
              />

              <button
                onClick={sendMessage}
                className="
                  px-8
                  rounded-2xl
                  bg-blue-600
                  hover:bg-blue-500
                  transition-all
                "
              >
                Send
              </button>

            </div>

          </div>

        </div>

      </div>

    </MainLayout>

  );
}

export default FixNowPage;