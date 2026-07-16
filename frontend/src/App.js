import "@/App.css";
import { useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Toaster } from "sonner";
import axios from "axios";
import { API } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import AuthCallback from "@/components/AuthCallback";
import Home from "@/pages/Home";
import Login from "@/pages/Login";
import QrClaim from "@/pages/QrClaim";
import Layout from "@/components/Layout";
import Dashboard from "@/pages/Dashboard";
import Messages from "@/pages/Messages";
import Projects from "@/pages/Projects";
import Assets from "@/pages/Assets";
import Integrations from "@/pages/Integrations";
import AiAssistant from "@/pages/AiAssistant";
import Profile from "@/pages/Profile";
import People from "@/pages/People";
import Notes from "@/pages/Notes";
import Activity from "@/pages/Activity";
import Downloads from "@/pages/Downloads";
import Meetings from "@/pages/Meetings";
import Call from "@/pages/Call";
import ProjectBoard from "@/pages/ProjectBoard";
import Settings from "@/pages/Settings";
import Admin from "@/pages/Admin";

function FullLoader() {
  return (
    <div className="stitch-wallpaper min-h-screen flex items-center justify-center">
      <div className="stitch-spinner" />
    </div>
  );
}

function Protected({ children }) {
  const { user } = useAuth();
  if (user === null) return <FullLoader />;
  if (user === false) return <Navigate to="/login" replace />;
  return children;
}

function AppRouter() {
  useLocation();
  if (window.location.hash?.includes("session_id=")) return <AuthCallback />;

  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Login />} />
      <Route path="/qr-login/claim" element={<QrClaim />} />
      <Route path="/call/:roomId" element={<Protected><Call /></Protected>} />
      <Route
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/messages" element={<Messages />} />
        <Route path="/projects" element={<Projects />} />
        <Route path="/projects/:projectId/board" element={<ProjectBoard />} />
        <Route path="/assets" element={<Assets />} />
        <Route path="/integrations" element={<Integrations />} />
        <Route path="/assistant" element={<AiAssistant />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/people" element={<People />} />
        <Route path="/notes" element={<Notes />} />
        <Route path="/activity" element={<Activity />} />
        <Route path="/downloads" element={<Downloads />} />
        <Route path="/meetings" element={<Meetings />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/admin" element={<Admin />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  useEffect(() => {
    axios.get(`${API}/seo`).then(({ data }) => {
      if (data.title) document.title = data.title;
      const setMeta = (name, content) => {
        if (!content) return;
        let el = document.querySelector(`meta[name="${name}"]`);
        if (!el) { el = document.createElement("meta"); el.setAttribute("name", name); document.head.appendChild(el); }
        el.setAttribute("content", content);
      };
      setMeta("description", data.description);
      setMeta("keywords", data.keywords);
    }).catch(() => {});
  }, []);

  return (
    <div className="App">
      <BrowserRouter>
        <AppRouter />
        <Toaster position="bottom-right" richColors />
      </BrowserRouter>
    </div>
  );
}
