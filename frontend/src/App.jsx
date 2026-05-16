import { Routes, Route } from "react-router-dom";

import LandingPage from "./screens/Landing/LandingPage";

import QuestionsPage from "./screens/Questions/QuestionsPage";

import ScanningPage from "./screens/Scanning/ScanningPage";

import ResultsPage from "./screens/Results/ResultsPage";

import FixNowPage from "./screens/FixAssistant/FixNowPage";

function App() {
  return (
    <Routes>

      <Route
        path="/"
        element={<LandingPage />}
      />

      <Route
        path="/questions"
        element={<QuestionsPage />}
      />

      <Route
        path="/scanning"
        element={<ScanningPage />}
      />

      <Route
        path="/results"
        element={<ResultsPage />}
      />

      <Route
        path="/fix"
        element={<FixNowPage />}
      />

    </Routes>
  );
}

export default App;