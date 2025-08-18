import { Routes, Route, Navigate } from "react-router-dom";
import Setup from "./pages/Setup";
import WaitingRoom from "./pages/WaitingRoom";
import Interview from "./pages/Interview";
import Feedback from "./pages/Feedback";
import "./styles/theme.css";


export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Setup />} />
      <Route path="/waiting" element={<WaitingRoom />} />
      <Route path="/interview" element={<Interview />} />
      <Route path="/feedback" element={<Feedback/>} />
      <Route path="/feedback/:sessionId" element={<Feedback />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
