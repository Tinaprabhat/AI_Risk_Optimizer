import { useMemo } from "react";

import { motion } from "framer-motion";

import MainLayout from "../../layouts/MainLayout";

import useAuditStore from "../../store/auditStore";

import ScoreCard from "../../components/cards/ScoreCard";

import ScoreRing from "../../components/radar/ScoreRing";

import LayerSection from "../../components/cards/LayerSection";

import SummaryCard from "../../components/cards/SummaryCard";

import PriorityIssueCard from "../../components/cards/PriorityIssueCard";

import ConclusionCard from "../../components/cards/ConclusionCard";

import { useNavigate } from "react-router-dom";

function ResultsPage() {

  const navigate = useNavigate();

  const auditResult = useAuditStore(
    (state) => state.auditResult
  );

  const checks = auditResult?.checks || {};

  // CONVERT OBJECT → ARRAY
  const checkArray = Object.values(checks);

  // ANALYTICS
  const totalChecks = checkArray.length;

  const passedChecks = checkArray.filter(
    (item) => item.status === "PASS"
  ).length;

  const failedChecks =
    totalChecks - passedChecks;

  const score =
    totalChecks > 0
      ? Math.round(
          (passedChecks / totalChecks) * 100
        )
      : 0;

  // PRIORITY ISSUES
  const priorityIssues = checkArray.filter(
    (item) => item.status === "FAIL"
  );

  // LAYER GROUPS
  const layerGroups = useMemo(() => {

    const groups = {

      "Layer 1": [],
      "Layer 2": [],
      "Layer 3": [],
      "Layer 4": [],
      "Layer 5": [],
      "Layer 6": [],
      "Layer 7": [],

    };

    checkArray.forEach((check) => {

      const checkName =
        check.check?.toLowerCase() || "";

      // LAYER 3
      if (
        checkName.startsWith("r13") ||
        checkName.startsWith("r15") ||
        checkName.startsWith("r16") ||
        checkName.startsWith("r17")
      ) {

        groups["Layer 3"].push(check);

      }

      // LAYER 4
      else if (
        checkName.startsWith("r23") ||
        checkName.startsWith("r25")
      ) {

        groups["Layer 4"].push(check);

      }

      // LAYER 1
      else if (
        checkName.startsWith("r1") ||
        checkName.startsWith("r2") ||
        checkName.startsWith("r3")
      ) {

        groups["Layer 1"].push(check);

      }

      // LAYER 2
      else if (
        checkName.startsWith("r4") ||
        checkName.startsWith("r5") ||
        checkName.startsWith("r6")
      ) {

        groups["Layer 2"].push(check);

      }

      // OTHER
      else {

        groups["Layer 7"].push(check);

      }

    });

    return groups;

  }, [checkArray]);

  // EMPTY STATE
  if (!auditResult) {

    return (

      <MainLayout>

        <div className="
          min-h-screen
          flex
          items-center
          justify-center
          text-white
          text-xl
        ">
          No audit data found.
        </div>

      </MainLayout>

    );
  }

  return (

    <MainLayout>

      <motion.div
        initial={{
          opacity: 0,
          y: 40,
        }}
        animate={{
          opacity: 1,
          y: 0,
        }}
        transition={{
          duration: 0.7,
        }}
        className="
          max-w-7xl
          mx-auto
          px-6
          py-20
        "
      >

        {/* HEADER */}
        <div className="mb-14">

          <div className="
            text-blue-400
            text-sm
            mb-4
          ">
            Audit Completed
          </div>

          <h1 className="
            text-4xl
            md:text-6xl
            font-bold
            mb-6
            leading-tight
          ">
            AI Visibility Report
          </h1>

          <p className="
            text-gray-400
            text-lg
            max-w-2xl
            leading-relaxed
          ">
            Store analyzed successfully.
          </p>

        </div>

        {/* STORE INFO */}
        <div className="
          bg-white/5
          border
          border-white/10
          rounded-2xl
          p-8
          mb-10
          backdrop-blur-xl
        ">

          <div className="
            text-sm
            text-gray-400
            mb-2
          ">
            Store URL
          </div>

          <div className="
            text-xl
            md:text-2xl
            font-semibold
            break-all
          ">
            {auditResult?.store_url}
          </div>

        </div>

        {/* HERO */}
        <div className="
          flex
          flex-col
          lg:flex-row
          items-center
          justify-between
          gap-12
          mb-16
        ">

          {/* LEFT */}
          <div>

            <div className="
              text-blue-400
              text-sm
              mb-4
            ">
              AI Readiness Score
            </div>

            <h2 className="
              text-4xl
              md:text-5xl
              font-bold
              mb-6
              leading-tight
            ">
              Your Store Visibility
              Analysis
            </h2>

            <p className="
              text-gray-400
              text-lg
              max-w-xl
              leading-relaxed
            ">
              This score represents how well
              AI systems can discover,
              understand, and recommend
              your ecommerce store.
            </p>

          </div>

          {/* RIGHT */}
          <ScoreRing score={score} />

        </div>

        {/* SCORE CARDS */}
        <div className="
          grid
          grid-cols-1
          md:grid-cols-3
          gap-6
          mb-16
        ">

          <ScoreCard
            title="Overall AI Visibility"
            value={`${score}%`}
            subtitle="Visibility readiness score"
          />

          <ScoreCard
            title="Passed Checks"
            value={passedChecks}
            subtitle="Successful audit checks"
          />

          <ScoreCard
            title="Failed Checks"
            value={failedChecks}
            subtitle="Issues requiring attention"
          />

        </div>

        {/* AI CONCLUSION */}
        <ConclusionCard
          score={score}
          checks={checkArray}
        />

        {/* AI INSIGHTS */}
        <div className="mb-20">

          <div className="mb-8">

            <h2 className="
              text-3xl
              font-bold
              mb-3
            ">
              Executive AI Insights
            </h2>

            <p className="
              text-gray-400
              leading-relaxed
              max-w-3xl
            ">
              High-level analysis of your
              store's AI visibility,
              discoverability,
              and semantic readiness.
            </p>

          </div>

          <div className="
            grid
            grid-cols-1
            md:grid-cols-3
            gap-6
          ">

            <SummaryCard
              title="AI Discoverability"
              severity={
                score >= 70
                  ? "success"
                  : score >= 40
                  ? "warning"
                  : "danger"
              }
              description={
                score >= 70
                  ? "Your store is highly discoverable by AI systems and search crawlers."
                  : score >= 40
                  ? "Your store has moderate AI discoverability but still lacks optimization in key areas."
                  : "Your store has weak AI discoverability and requires significant optimization."
              }
            />

            <SummaryCard
              title="Semantic Understanding"
              severity={
                failedChecks <= 2
                  ? "success"
                  : failedChecks <= 5
                  ? "warning"
                  : "danger"
              }
              description={
                failedChecks <= 2
                  ? "Your semantic structure is strong and understandable by AI systems."
                  : failedChecks <= 5
                  ? "Some semantic signals are missing or weak."
                  : "Your semantic architecture is weak and inconsistent."
              }
            />

            <SummaryCard
              title="Recommendation Readiness"
              severity={
                score >= 75
                  ? "success"
                  : score >= 50
                  ? "warning"
                  : "danger"
              }
              description={
                score >= 75
                  ? "Your store is highly recommendation-ready for AI commerce systems."
                  : score >= 50
                  ? "Your store is partially optimized for AI recommendations."
                  : "Your store lacks critical trust and recommendation signals."
              }
            />

          </div>

        </div>

        {/* PRIORITY ISSUES */}
        {priorityIssues.length > 0 && (

          <div className="mb-20">

            <div className="mb-8">

              <h2 className="
                text-3xl
                font-bold
                mb-3
              ">
                Priority Issues
              </h2>

              <p className="
                text-gray-400
                max-w-3xl
                leading-relaxed
              ">
                These issues have the
                highest impact on your
                store’s AI visibility
                and recommendation readiness.
              </p>

            </div>

            <div className="
              grid
              grid-cols-1
              lg:grid-cols-2
              gap-6
            ">

              {priorityIssues
                .slice(0, 4)
                .map((issue) => (

                  <PriorityIssueCard
                    key={issue.check}
                    issue={issue}
                  />

              ))}

            </div>

          </div>

        )}

        {/* LAYERED AUDIT */}

        <LayerSection
          title="Layer 1"
          description="
            Crawlability, robots.txt,
            sitemap accessibility,
            and AI discoverability.
          "
          checks={layerGroups["Layer 1"]}
        />

        <LayerSection
          title="Layer 2"
          description="
            Metadata structure,
            semantic markup,
            and machine readability.
          "
          checks={layerGroups["Layer 2"]}
        />

        <LayerSection
          title="Layer 3"
          description="
            Semantic positioning,
            embedding quality,
            and AI contextual understanding.
          "
          checks={layerGroups["Layer 3"]}
        />

        <LayerSection
          title="Layer 4"
          description="
            Brand clarity,
            trust signals,
            and recommendation readiness.
          "
          checks={layerGroups["Layer 4"]}
        />

        <LayerSection
          title="Other Checks"
          description="
            Additional AI visibility
            diagnostics and evaluations.
          "
          checks={layerGroups["Layer 7"]}
        />

        {/* FIX NOW BUTTON */}

        <div className="
          mt-24
          flex
          justify-center
        ">

          <button
            onClick={() =>
              navigate("/fix")
            }
            className="
              px-10
              py-5
              rounded-2xl
              bg-blue-600
              hover:bg-blue-500
              transition-all
              duration-300
              text-lg
              font-semibold
              shadow-2xl
              shadow-blue-500/20
            "
          >
            Fix Now →
          </button>

        </div>

      </motion.div>

    </MainLayout>

  );
}

export default ResultsPage;