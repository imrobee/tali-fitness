import { Route, Routes } from "react-router";
import { BottomNav } from "./components/BottomNav";
import { SignInGate } from "./components/SignInGate";
import { ScrollToTop } from "./components/ScrollToTop";
import { DashboardPage } from "./pages/DashboardPage";
import { ActivitiesPage } from "./pages/ActivitiesPage";
import { NutritionPage } from "./pages/DayPages";
import { MePage } from "./pages/MePage";
import { TourProvider } from "./tour/TourProvider";

// Four pages and one bottom navigation (UI_SPEC.md section 1). Everything sits behind
// the sign-in gate: until the browser is signed in, no page calls the API.
export default function App() {
  return (
    <SignInGate>
      {/* The demo's guided tour; on Rob's own app it never starts. */}
      <TourProvider>
        <ScrollToTop />
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/activities" element={<ActivitiesPage />} />
          <Route path="/nutrition" element={<NutritionPage />} />
          <Route path="/me" element={<MePage />} />
          <Route path="*" element={<DashboardPage />} />
        </Routes>
        <BottomNav />
      </TourProvider>
    </SignInGate>
  );
}
