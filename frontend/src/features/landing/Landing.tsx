import { PageShell } from "../../app/layouts";
import Hero from "./Hero";
import { CtaBand, Demo, Faq, Finds, How, Languages, Roles, Safety, Statement } from "./Sections";

export default function Landing() {
  return (
    <PageShell>
      <main>
        <Hero />
        <Finds />
        <How />
        <Statement />
        <Safety />
        <Demo />
        <Languages />
        <Roles />
        <Faq />
        <CtaBand />
      </main>
    </PageShell>
  );
}
