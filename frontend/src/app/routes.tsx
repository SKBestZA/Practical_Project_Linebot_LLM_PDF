import { createBrowserRouter, Navigate } from "react-router";
import { DashboardLayout } from "./components/DashboardLayout";
import { Overview } from "./components/Overview";
import { Policies } from "./components/Policies";
import { Employees } from "./components/Employees";
import { Settings } from "./components/Settings";
import { Login } from "./components/Login";
import { LiffLogin } from "./components/LiffLogin";
import { ProtectedRoute } from "./components/ProtectedRoute";

export const router = createBrowserRouter([
  {
    path: "/login",
    Component: Login,
  },
  {
    path: "/liff/login",
    Component: LiffLogin,
  },
  {
    path: "/",
    element: (
      <ProtectedRoute>
        <DashboardLayout />
      </ProtectedRoute>
    ),
    children: [
      { index: true, Component: Overview },
      { path: "policies", Component: Policies },
      { path: "employees", Component: Employees },
      { path: "settings", Component: Settings },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);