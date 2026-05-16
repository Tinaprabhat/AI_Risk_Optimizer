import { useEffect, useRef } from "react";

import { useNavigate } from "react-router-dom";

import MainLayout from "../../layouts/MainLayout";

import useAuditStore from "../../store/auditStore";

import { runAudit } from "../../services/auditService";

function ScanningPage() {

  const navigate = useNavigate();

  // PREVENT DOUBLE EXECUTION
  const startedRef = useRef(false);

  const storeUrl = useAuditStore(
    (state) => state.storeUrl
  );

  const questions = useAuditStore(
    (state) => state.questions
  );

  const setAuditResult = useAuditStore(
    (state) => state.setAuditResult
  );

  const setScanStatus = useAuditStore(
    (state) => state.setScanStatus
  );

  const addProgressLog = useAuditStore(
    (state) => state.addProgressLog
  );

  const progressLogs = useAuditStore(
    (state) => state.progressLogs
  );

  const setProgressLogs = useAuditStore(
    (state) => state.setProgressLogs
  );

  useEffect(() => {

    // BLOCK DUPLICATE RUNS
    if (startedRef.current) return;

    startedRef.current = true;

    const startAudit = async () => {

      try {

        // RESET LOGS
        setProgressLogs([]);

        setScanStatus("running");

        const payload = {

          url: storeUrl,

          merchant_description:
            questions.differentiator,

          category: questions.category,

          customer: questions.customer,

          differentiator:
            questions.differentiator,

          tone: questions.tone,
        };

        console.log(
          "AUDIT PAYLOAD:",
          payload
        );

        // LIVE STAGES
        const fakeStages = [

          "Fetching homepage...",

          "Analyzing crawlability...",

          "Checking structured data...",

          "Running semantic analysis...",

          "Evaluating trust signals...",

          "Computing AI visibility score...",

          "Generating AI recommendations...",

        ];

        for (const stage of fakeStages) {

          addProgressLog(stage);

          await new Promise((resolve) =>
            setTimeout(resolve, 900)
          );
        }

        // REAL BACKEND CALL
        const result = await runAudit(
          payload
        );

        console.log(
          "AUDIT RESULT:",
          result
        );

        setAuditResult(result);

        setScanStatus("completed");

        navigate("/results");

      } catch (error) {

        console.error(error);

        setScanStatus("failed");

        addProgressLog(
          "Audit failed. Please try again."
        );
      }
    };

    startAudit();

  }, []);

  return (
    <MainLayout>

      <div className="
        min-h-screen
        flex
        flex-col
        items-center
        justify-center
        text-center
        px-6
        py-20
      ">

        {/* ADVANCED SCANNER */}
        <div className="
          relative
          w-52
          h-52
          flex
          items-center
          justify-center
          mb-14
        ">

          {/* OUTER PULSE */}
          <div className="
            absolute
            inset-0
            rounded-full
            bg-blue-500/10
            animate-ping
          " />

          {/* MIDDLE RING */}
          <div className="
            absolute
            inset-4
            rounded-full
            border
            border-blue-400/20
          " />

          {/* SPINNING RING */}
          <div className="
            absolute
            inset-0
            rounded-full
            border-[6px]
            border-blue-500/20
            border-t-cyan-400
            animate-spin
          " />

          {/* INNER GLOW */}
          <div className="
            w-24
            h-24
            rounded-full
            bg-gradient-to-br
            from-cyan-400
            to-blue-600
            shadow-[0_0_60px_rgba(59,130,246,0.8)]
            animate-pulse
          " />

        </div>

        {/* TITLE */}
        <h1 className="
          text-6xl
          font-bold
          mb-6
        ">
          Scanning Your Store
        </h1>

        {/* DESCRIPTION */}
        <p className="
          text-gray-400
          text-lg
          max-w-2xl
          mb-14
          leading-relaxed
        ">
          Our AI system is analyzing
          your ecommerce store for
          semantic visibility,
          structured data quality,
          AI discoverability,
          and recommendation readiness.
        </p>

        {/* LIVE TERMINAL */}
        <div className="
          w-full
          max-w-3xl
          bg-black/30
          border
          border-white/10
          rounded-2xl
          overflow-hidden
          backdrop-blur-2xl
          shadow-2xl
        ">

          {/* TERMINAL HEADER */}
          <div className="
            flex
            items-center
            gap-2
            px-5
            py-4
            border-b
            border-white/10
            bg-white/5
          ">

            <div className="
              w-3
              h-3
              rounded-full
              bg-red-400
            " />

            <div className="
              w-3
              h-3
              rounded-full
              bg-yellow-400
            " />

            <div className="
              w-3
              h-3
              rounded-full
              bg-green-400
            " />

            <div className="
              ml-4
              text-sm
              text-gray-400
            ">
              AI Visibility Scanner
            </div>

          </div>

          {/* TERMINAL BODY */}
          <div className="
            p-6
            space-y-4
            max-h-[400px]
            overflow-auto
            text-left
          ">

            {progressLogs.map(
              (log, index) => (

                <div
                  key={index}
                  className="
                    flex
                    items-start
                    gap-3
                    text-gray-300
                    animate-pulse
                  "
                >

                  <div className="
                    text-cyan-400
                    mt-[2px]
                  ">
                    →
                  </div>

                  <div className="
                    font-mono
                    text-sm
                    leading-relaxed
                  ">
                    {log}
                  </div>

                </div>

              )
            )}

          </div>

        </div>

      </div>

    </MainLayout>
  );
}

export default ScanningPage;