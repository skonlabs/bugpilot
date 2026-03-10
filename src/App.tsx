import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AuthProvider } from "@/contexts/AuthContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";

import PublicLayout from "@/components/layouts/PublicLayout";
import DashboardLayout from "@/components/layouts/DashboardLayout";
import AdminLayout from "@/components/layouts/AdminLayout";
import DocsLayout from "@/components/layouts/DocsLayout";

import Index from "@/pages/Index";
import NotFound from "@/pages/NotFound";
import SignIn from "@/pages/auth/SignIn";
import SignUp from "@/pages/auth/SignUp";
import ForgotPassword from "@/pages/auth/ForgotPassword";
import ResetPassword from "@/pages/auth/ResetPassword";
import Product from "@/pages/public/Product";
import HowItWorks from "@/pages/public/HowItWorks";
import Pricing from "@/pages/public/Pricing";
import DownloadPage from "@/pages/public/DownloadPage";

import Dashboard from "@/pages/dashboard/Dashboard";
import Credentials from "@/pages/dashboard/Credentials";
import Settings from "@/pages/dashboard/Settings";
import Downloads from "@/pages/dashboard/Downloads";

import AdminDashboard from "@/pages/admin/AdminDashboard";
import AdminUsers from "@/pages/admin/AdminUsers";
import AdminCredentials from "@/pages/admin/AdminCredentials";
import AdminAuditLogs from "@/pages/admin/AdminAuditLogs";
import AdminReleases from "@/pages/admin/AdminReleases";

import DocsPage from "@/pages/docs/DocsPage";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            {/* Public */}
            <Route element={<PublicLayout />}>
              <Route path="/" element={<Index />} />
              <Route path="/product" element={<Product />} />
              <Route path="/how-it-works" element={<HowItWorks />} />
              <Route path="/pricing" element={<Pricing />} />
              <Route path="/download" element={<DownloadPage />} />
            </Route>

            {/* Auth */}
            <Route path="/sign-in" element={<SignIn />} />
            <Route path="/sign-up" element={<SignUp />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/reset-password" element={<ResetPassword />} />

            {/* Docs */}
            <Route path="/docs" element={<DocsLayout />}>
              <Route index element={<DocsPage />} />
              <Route path=":slug" element={<DocsPage />} />
            </Route>

            {/* Dashboard (Protected) */}
            <Route element={<ProtectedRoute><DashboardLayout /></ProtectedRoute>}>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/dashboard/credentials" element={<Credentials />} />
              <Route path="/dashboard/settings" element={<Settings />} />
              <Route path="/dashboard/downloads" element={<Downloads />} />
            </Route>

            {/* Admin (Protected + Admin Only) */}
            <Route element={<ProtectedRoute adminOnly><AdminLayout /></ProtectedRoute>}>
              <Route path="/admin" element={<AdminDashboard />} />
              <Route path="/admin/users" element={<AdminUsers />} />
              <Route path="/admin/credentials" element={<AdminCredentials />} />
              <Route path="/admin/audit-logs" element={<AdminAuditLogs />} />
              <Route path="/admin/releases" element={<AdminReleases />} />
            </Route>

            <Route path="*" element={<NotFound />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
