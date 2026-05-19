import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuditProvider } from "./context/AuditContext";
import Landing  from "./screens/Landing";
import McqForm  from "./screens/McqForm";
import Scanning from "./screens/Scanning";
import Results  from "./screens/Results";
import AiMirror from "./screens/AiMirror";
import FixNow   from "./screens/FixNow";

export default function App() {
  return (
    <AuditProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/"        element={<Landing />}  />
          <Route path="/mcq"     element={<McqForm />}  />
          <Route path="/scan"    element={<Scanning />} />
          <Route path="/results" element={<Results />}  />
          <Route path="/mirror"  element={<AiMirror />} />
          <Route path="/fix"     element={<FixNow />}   />
          <Route path="*"        element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuditProvider>
  );
}