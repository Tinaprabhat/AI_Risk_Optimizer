import MainLayout from "../../layouts/MainLayout";

import Navbar from "../../components/navbar/Navbar";
import HeroSection from "../../components/shared/HeroSection";
import UrlInput from "../../components/shared/UrlInput";
import PlatformPills from "../../components/shared/PlatformPills";

function LandingPage() {
  return (
    <MainLayout>

      <div className="max-w-7xl mx-auto px-6 py-10">

        <Navbar />

        <HeroSection />

        <UrlInput />

        <PlatformPills />

      </div>

    </MainLayout>
  );
}

export default LandingPage;