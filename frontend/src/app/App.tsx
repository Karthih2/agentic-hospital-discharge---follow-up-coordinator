import { Navigate, Route, Routes } from "react-router-dom";
import { AdminLogin } from "../features/admin/AdminLogin";
import { AdminAudit, AdminDoctors, AdminHubs, AdminOverview, AdminRouting, AdminSystem } from "../features/admin/pages";
import { AuthPage, LanguagePage, StartPage } from "../features/auth/Auth";
import { DoctorPatients, DoctorQueue, ReviewDetail } from "../features/doctor/Doctor";
import { DoctorPlans, PlanEditor } from "../features/doctor/Plans";
import { AdminPlans } from "../features/admin/PlansAdmin";
import { HubHome, Members, Notifications } from "../features/family-hub/FamilyHub";
import { Upload } from "../features/family-hub/Upload";
import Landing from "../features/landing/Landing";
import { Privacy, Terms } from "../features/legal/Legal";
import Manual from "../features/plan/Manual";
import Plan from "../features/plan/Plan";
import Providers from "../features/providers/Providers";
import { RequireRole } from "./guards";
import { AppShell } from "./layouts";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/terms" element={<Terms />} />
      <Route path="/privacy" element={<Privacy />} />
      <Route path="/login" element={<AuthPage initial="login" />} />
      <Route path="/register" element={<AuthPage initial="register" />} />
      {/* The hospital admin center: its own login, never linked from any page */}
      <Route path="/admin" element={<AdminLogin />} />

      <Route element={<RequireRole />}>
        <Route element={<AppShell />}>
          <Route path="/start" element={<StartPage />} />
          <Route path="/language" element={<LanguagePage />} />
        </Route>
      </Route>

      <Route path="/hub" element={<RequireRole roles={["patient", "family"]} />}>
        <Route element={<AppShell />}>
          <Route index element={<HubHome />} />
          <Route path="members" element={<Members />} />
          <Route path="notifications" element={<Notifications />} />
          <Route path="plan/:pid" element={<Plan />} />
          <Route path="upload/:pid" element={<Upload />} />
          <Route path="manual/:pid" element={<Manual />} />
          <Route path="providers/:taskId" element={<Providers />} />
        </Route>
      </Route>

      <Route path="/doctor" element={<RequireRole roles={["doctor"]} loginTo="/login?as=doctor" />}>
        <Route element={<AppShell />}>
          <Route index element={<DoctorQueue />} />
          <Route path="review/:id" element={<ReviewDetail />} />
          <Route path="patients" element={<DoctorPatients />} />
          <Route path="plans" element={<DoctorPlans />} />
          <Route path="plans/:id" element={<PlanEditor />} />
        </Route>
      </Route>

      <Route path="/admin" element={<RequireRole roles={["admin"]} loginTo="/admin" />}>
        <Route element={<AppShell />}>
          <Route path="overview" element={<AdminOverview />} />
          <Route path="doctors" element={<AdminDoctors />} />
          <Route path="routing" element={<AdminRouting />} />
          <Route path="plans" element={<AdminPlans />} />
          <Route path="hubs" element={<AdminHubs />} />
          <Route path="audit" element={<AdminAudit />} />
          <Route path="system" element={<AdminSystem />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
