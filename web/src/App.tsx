import { Navigate, Route, Routes } from "react-router-dom";

import { Shell } from "./components/Shell";
import { AcceptancePage } from "./pages/Acceptance";
import { RecordsPage } from "./pages/Records";
import { WorkspacePage } from "./pages/Workspace";

export function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<WorkspacePage />} />
        <Route path="/s/:sessionId" element={<WorkspacePage />} />
        <Route path="/records" element={<RecordsPage />} />
        <Route path="/acceptance" element={<AcceptancePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  );
}
